import { useRef } from "react";
import { Upload } from "lucide-react";
import s from "./UploadDropzone.module.css";

/** 클립이 하나도 없을 때 뷰어 자리를 채우는 큰 놓기 영역. */
export function UploadDropzone({ onFiles }: { onFiles: (files: FileList) => void }) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <div className={s.zone}>
      <span className={s.icon}>
        <Upload size={26} aria-hidden="true" />
      </span>
      <p className={s.title}>영상을 여기에 끌어다 놓으세요</p>
      <p className="muted">여러 개를 한 번에 올릴 수 있습니다 · mp4, mov, mkv</p>
      <button type="button" className="btn" onClick={() => input.current?.click()}>
        파일 고르기
      </button>
      <input
        ref={input}
        type="file"
        accept="video/*,.mkv,.mts,.m2ts"
        multiple
        hidden
        onChange={(event) => {
          if (event.target.files) {
            onFiles(event.target.files);
          }
          event.target.value = "";
        }}
      />
    </div>
  );
}
