/** POST /videos 응답. OpenAPI VideoCreated와 같다. */

export interface VideoMeta {
  id: string;
  filename: string;
  content_type: string | null;
  duration: number | null;
  width: number | null;
  height: number | null;
}
