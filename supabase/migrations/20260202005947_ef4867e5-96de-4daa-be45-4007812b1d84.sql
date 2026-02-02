-- Create storage bucket for media uploads
INSERT INTO storage.buckets (id, name, public)
VALUES ('media-uploads', 'media-uploads', true)
ON CONFLICT (id) DO NOTHING;

-- Policy for anyone to read media files (public bucket)
CREATE POLICY "Anyone can view media files"
ON storage.objects
FOR SELECT
USING (bucket_id = 'media-uploads');

-- Policy for anyone to upload media files
CREATE POLICY "Anyone can upload media files"
ON storage.objects
FOR INSERT
WITH CHECK (bucket_id = 'media-uploads');

-- Policy for anyone to delete their uploaded media files
CREATE POLICY "Anyone can delete media files"
ON storage.objects
FOR DELETE
USING (bucket_id = 'media-uploads');