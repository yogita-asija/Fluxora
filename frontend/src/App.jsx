import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import ProtectedRoute from "./components/ProtectedRoute.jsx";
import Inventory from "./pages/Inventory.jsx";
import Login from "./pages/Login.jsx";
import OrderDetail from "./pages/OrderDetail.jsx";
import Orders from "./pages/Orders.jsx";
import Products from "./pages/Products.jsx";
import Register from "./pages/Register.jsx";
import SystemHealth from "./pages/SystemHealth.jsx";

// Recharts is the heaviest dependency; load it only when Analytics is opened.
const Analytics = lazy(() => import("./pages/Analytics.jsx"));

export default function App() {
  return (
    <Routes>
      <Route path="login" element={<Login />} />
      <Route path="register" element={<Register />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/orders" replace />} />
          <Route path="orders" element={<Orders />} />
          <Route path="orders/:orderId" element={<OrderDetail />} />
          <Route path="products" element={<Products />} />
          <Route path="inventory" element={<Inventory />} />
          <Route
            path="analytics"
            element={
              <Suspense fallback={<p className="text-sm text-slate-500">Loading charts…</p>}>
                <Analytics />
              </Suspense>
            }
          />
          <Route path="system-health" element={<SystemHealth />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/orders" replace />} />
    </Routes>
  );
}
