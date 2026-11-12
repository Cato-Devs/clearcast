import { BrowserRouter, Route, Routes } from "react-router";
import { AppProvider } from "./AppContext.jsx";
import Layout from "./Layout.jsx";
import AboutPage from "./pages/AboutPage.jsx";
import AccountPage from "./pages/AccountPage.jsx";
import AdminPage from "./pages/AdminPage.jsx";
import AlertsPage from "./pages/AlertsPage.jsx";
import CurrentWeatherPage from "./pages/CurrentWeatherPage.jsx";
import LocationPage from "./pages/LocationPage.jsx";
import LocationsPage from "./pages/LocationsPage.jsx";
import MapPage from "./pages/MapPage.jsx";
import NotFoundPage from "./pages/NotFoundPage.jsx";

export default function App() {
  return (
    <BrowserRouter>
      <AppProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<MapPage />} />
            <Route path="weather" element={<CurrentWeatherPage />} />
            <Route path="locations" element={<LocationsPage />} />
            <Route path="locations/:name" element={<LocationPage />} />
            <Route path="alerts" element={<AlertsPage />} />
            <Route path="account" element={<AccountPage />} />
            <Route path="about" element={<AboutPage />} />
            <Route path="admin" element={<AdminPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </AppProvider>
    </BrowserRouter>
  );
}
