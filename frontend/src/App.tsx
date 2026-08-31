import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
import { History } from "./pages/History";
import { NewPayPeriod } from "./pages/NewPayPeriod";
import { Reconciliation } from "./pages/Reconciliation";
import { ReviewPayslip } from "./pages/ReviewPayslip";
import { ReviewShifts } from "./pages/ReviewShifts";
import { Settings } from "./pages/Settings";
import { navigate, useLocationPath } from "./services/navigation";

export default function App() {
  const path = useLocationPath();
  let page;
  if (path === "/") page = <Dashboard />;
  else if (path === "/new") page = <NewPayPeriod />;
  else if (path === "/history") page = <History />;
  else if (path === "/settings") page = <Settings />;
  else if (/^\/pay-periods\/[^/]+\/payslip$/.test(path)) page = <ReviewPayslip />;
  else if (/^\/pay-periods\/[^/]+\/shifts$/.test(path)) page = <ReviewShifts />;
  else if (/^\/pay-periods\/[^/]+\/reconciliation$/.test(path)) page = <Reconciliation />;
  else {
    navigate("/", true);
    page = <Dashboard />;
  }
  return <Layout>{page}</Layout>;
}
