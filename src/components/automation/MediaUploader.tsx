import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { uploadMedia, deleteMedia, formatFileSize, type UploadedMedia } from "@/services/mediaService";
import { toast } from "sonner";
import { 
  Mic, 
  Image, 
  Video, 
  Upload, 
  X, 
  Loader2,
  FileAudio,
  FileImage,
  FileVideo
} from "lucide-react";

interface MediaUploaderProps {
  uploadedFiles: UploadedMedia[];
  onFilesChange: (files: UploadedMedia[]) => void;
  automationId?: string;
}

const ACCEPTED_TYPES = {
  audio: ".mp3,.wav,.m4a,.ogg,.webm",
  image: ".png,.jpg,.jpeg,.webp,.gif",
  video: ".mp4,.webm,.mov",
};

const ALL_ACCEPTED = Object.values(ACCEPTED_TYPES).join(",");

export function MediaUploader({ uploadedFiles, onFilesChange, automationId }: MediaUploaderProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleFileUpload = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    setIsUploading(true);
    const newFiles: UploadedMedia[] = [];

    try {
      for (const file of Array.from(files)) {
        // Validate file size (max 50MB)
        if (file.size > 50 * 1024 * 1024) {
          toast.error(`Arquivo ${file.name} é muito grande (máx 50MB)`);
          continue;
        }

        const uploaded = await uploadMedia(file, automationId);
        newFiles.push(uploaded);
      }

      if (newFiles.length > 0) {
        onFilesChange([...uploadedFiles, ...newFiles]);
        toast.success(`${newFiles.length} arquivo(s) enviado(s)`);
      }
    } catch (error) {
      console.error("Upload error:", error);
      toast.error("Erro ao fazer upload");
    } finally {
      setIsUploading(false);
    }
  }, [uploadedFiles, onFilesChange, automationId]);

  const handleRemoveFile = async (fileId: string) => {
    try {
      await deleteMedia(fileId);
      onFilesChange(uploadedFiles.filter(f => f.id !== fileId));
      toast.success("Arquivo removido");
    } catch (error) {
      console.error("Delete error:", error);
      toast.error("Erro ao remover arquivo");
    }
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    handleFileUpload(e.dataTransfer.files);
  }, [handleFileUpload]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const getFileIcon = (type: string) => {
    switch (type) {
      case 'audio': return <FileAudio className="h-4 w-4 text-info" />;
      case 'video': return <FileVideo className="h-4 w-4 text-accent" />;
      default: return <FileImage className="h-4 w-4 text-success" />;
    }
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Envie áudio, imagens ou vídeos para a IA analisar:
      </p>

      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={`
          relative border-2 border-dashed rounded-lg p-6 transition-colors
          ${isDragOver 
            ? 'border-primary bg-primary/5' 
            : 'border-muted-foreground/25 hover:border-primary/50'
          }
        `}
      >
        <input
          type="file"
          accept={ALL_ACCEPTED}
          multiple
          onChange={(e) => handleFileUpload(e.target.files)}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          disabled={isUploading}
        />

        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex gap-3">
            <div className="p-2 rounded-full bg-info/10">
              <Mic className="h-5 w-5 text-info" />
            </div>
            <div className="p-2 rounded-full bg-success/10">
              <Image className="h-5 w-5 text-success" />
            </div>
            <div className="p-2 rounded-full bg-accent/10">
              <Video className="h-5 w-5 text-accent" />
            </div>
          </div>

          {isUploading ? (
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-sm">Enviando...</span>
            </div>
          ) : (
            <>
              <p className="text-sm font-medium">
                Arraste arquivos ou clique para selecionar
              </p>
              <p className="text-xs text-muted-foreground">
                Áudio (MP3, WAV) • Imagem (PNG, JPG) • Vídeo (MP4, WebM)
              </p>
            </>
          )}
        </div>
      </div>

      {/* Uploaded files list */}
      {uploadedFiles.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-medium">Arquivos enviados:</p>
          <div className="space-y-2">
            {uploadedFiles.map((file) => (
              <Card key={file.id} className="p-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {getFileIcon(file.file_type)}
                    <div>
                      <p className="text-sm font-medium truncate max-w-[200px]">
                        {file.file_name}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatFileSize(file.file_size)}
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleRemoveFile(file.id)}
                    className="h-8 w-8 text-muted-foreground hover:text-destructive"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
