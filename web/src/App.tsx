import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { ToastProvider } from '@/components/Toast'
import CaseDetailPage from '@/pages/CaseDetail'
import CasesPage from '@/pages/Cases'
import DashboardPage from '@/pages/Dashboard'
import LoginPage from '@/pages/Login'
import ReconciliationPage from '@/pages/Reconciliation'
import ReportsPage from '@/pages/Reports'
import ReviewPage from '@/pages/Review'

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<DashboardPage />} />
            <Route path="/cases" element={<CasesPage />} />
            <Route path="/cases/:caseId" element={<CaseDetailPage />} />
            <Route path="/cases/:caseId/reconciliation" element={<ReconciliationPage />} />
            <Route path="/cases/:caseId/review" element={<ReviewPage />} />
            <Route path="/cases/:caseId/reports" element={<ReportsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  )
}
