import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "../components/AppLayout";
import { MasterEditorPage } from "../pages/MasterEditorPage";
import { MastersPage } from "../pages/MastersPage";
import { RunsPage } from "../pages/RunsPage";
import { TailoringPage } from "../pages/TailoringPage";

export function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<Navigate to="/masters" replace />} />
        <Route path="/masters" element={<MastersPage />} />
        <Route path="/masters/:masterId" element={<MasterEditorPage />} />
        <Route path="/tailoring" element={<TailoringPage />} />
        <Route path="/runs" element={<RunsPage />} />
      </Routes>
    </AppLayout>
  );
}
