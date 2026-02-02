import { supabase } from "@/integrations/supabase/client";
import type { MediaType } from "@/types/automation";

export interface UploadedMedia {
  id: string;
  file_type: MediaType;
  file_url: string;
  file_name: string;
  file_size: number;
}

/**
 * Upload a file to the media-uploads bucket
 */
export async function uploadMedia(
  file: File,
  automationId?: string
): Promise<UploadedMedia> {
  const fileType = getMediaType(file);
  const fileName = `${Date.now()}-${file.name}`;
  const filePath = automationId 
    ? `${automationId}/${fileName}` 
    : `temp/${fileName}`;

  // Upload to storage
  const { error: uploadError } = await supabase.storage
    .from('media-uploads')
    .upload(filePath, file);

  if (uploadError) {
    console.error("Upload error:", uploadError);
    throw new Error("Erro ao fazer upload do arquivo");
  }

  // Get public URL
  const { data: urlData } = supabase.storage
    .from('media-uploads')
    .getPublicUrl(filePath);

  // Save to media_uploads table
  const { data, error: dbError } = await supabase
    .from('media_uploads')
    .insert({
      file_type: fileType,
      file_url: urlData.publicUrl,
      file_name: file.name,
      file_size: file.size,
      automation_id: automationId || null,
    })
    .select()
    .single();

  if (dbError) {
    console.error("DB error:", dbError);
    throw new Error("Erro ao salvar registro do arquivo");
  }

  return {
    id: data.id,
    file_type: data.file_type as MediaType,
    file_url: data.file_url,
    file_name: data.file_name || file.name,
    file_size: data.file_size || file.size,
  };
}

/**
 * Delete a media file from storage and database
 */
export async function deleteMedia(mediaId: string): Promise<void> {
  // Get the media record first
  const { data: media, error: fetchError } = await supabase
    .from('media_uploads')
    .select('file_url')
    .eq('id', mediaId)
    .single();

  if (fetchError || !media) {
    throw new Error("Arquivo não encontrado");
  }

  // Extract file path from URL
  const url = new URL(media.file_url);
  const pathParts = url.pathname.split('/media-uploads/');
  const filePath = pathParts[1];

  if (filePath) {
    // Delete from storage
    const { error: storageError } = await supabase.storage
      .from('media-uploads')
      .remove([filePath]);

    if (storageError) {
      console.error("Storage delete error:", storageError);
    }
  }

  // Delete from database
  const { error: dbError } = await supabase
    .from('media_uploads')
    .delete()
    .eq('id', mediaId);

  if (dbError) {
    throw new Error("Erro ao remover registro do arquivo");
  }
}

/**
 * Get media type from file
 */
function getMediaType(file: File): MediaType {
  if (file.type.startsWith('audio/')) return 'audio';
  if (file.type.startsWith('video/')) return 'video';
  if (file.type.startsWith('image/')) return 'image';
  
  // Fallback based on extension
  const ext = file.name.split('.').pop()?.toLowerCase();
  if (['mp3', 'wav', 'm4a', 'ogg', 'webm'].includes(ext || '')) return 'audio';
  if (['mp4', 'webm', 'mov', 'avi'].includes(ext || '')) return 'video';
  
  return 'image';
}

/**
 * Format file size for display
 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
