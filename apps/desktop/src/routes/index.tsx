import { createBrowserRouter } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import { DashboardLayout } from '../layout/DashboardLayout';
import { DashboardPage } from '../features/dashboard/pages/DashboardPage';
import { AssistantPage } from '../features/assistant/pages/AssistantPage';
import { KnowledgePage } from '../features/knowledge/pages/KnowledgePage';
import { ProjectsPage } from '../features/projects/pages/ProjectsPage';
import { DeveloperPage } from '../features/developer/pages/DeveloperPage';
import { PluginsPage } from '../features/plugins/pages/PluginsPage';
import { SettingsPage } from '../features/settings/pages/SettingsPage';
import { MissionCenterPage } from '../pages/MissionCenter/MissionCenterPage';
import { CognitiveDashboardPage } from '../pages/CognitiveDashboard/CognitiveDashboardPage';

// Command Center is heavy (React Three Fiber + ATLAS) — load it lazily.
const CommandCenterPage = lazy(() =>
  import('../features/command-center/CommandCenterPage').then((m) => ({ default: m.CommandCenterPage })),
);

const CommandCenterFallback = () => (
  <div className="cc-root fixed inset-0 flex items-center justify-center text-cyan-glow font-mono text-xs tracking-[0.3em] uppercase">
    <span className="w-2 h-2 rounded-full bg-cyan-glow animate-ping mr-3" />
    Booting FRIDAY Command Center…
  </div>
);

export const router = createBrowserRouter([
  {
    path: '/command',
    element: (
      <Suspense fallback={<CommandCenterFallback />}>
        <CommandCenterPage />
      </Suspense>
    ),
  },
  {
    path: '/',
    element: <DashboardLayout />,
    children: [
      {
        path: '/',
        element: <DashboardPage />,
      },
      {
        path: '/assistant',
        element: <AssistantPage />,
      },
      {
        path: '/missions',
        element: <MissionCenterPage />,
      },
      {
        path: '/cognitive',
        element: <CognitiveDashboardPage />,
      },
      {
        path: '/knowledge',
        element: <KnowledgePage />,
      },
      {
        path: '/projects',
        element: <ProjectsPage />,
      },
      {
        path: '/developer',
        element: <DeveloperPage />,
      },
      {
        path: '/plugins',
        element: <PluginsPage />,
      },
      {
        path: '/settings',
        element: <SettingsPage />,
      },
    ],
  },
]);
