import { createBrowserRouter, Link } from "react-router";
import { HomePage } from "./routes/HomePage";
import { ProjectEditor } from "./routes/ProjectEditor";

function NotFound() {
  return (
    <main style={{ padding: 48, textAlign: "center" }}>
      <p className="muted">없는 화면입니다.</p>
      <Link to="/">프로젝트 목록으로</Link>
    </main>
  );
}

export const router = createBrowserRouter([
  { path: "/", element: <HomePage /> },
  { path: "/p/:projectId", element: <ProjectEditor /> },
  { path: "/p/:projectId/:step", element: <ProjectEditor /> },
  { path: "*", element: <NotFound /> },
]);
