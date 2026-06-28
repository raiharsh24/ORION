import { createBrowserRouter } from 'react-router-dom';
import { DashboardLayout } from '../layout/DashboardLayout';
import { DashboardPage } from '../features/dashboard/pages/DashboardPage';
import { AssistantPage } from '../features/assistant/pages/AssistantPage';
import { KnowledgePage } from '../features/knowledge/pages/KnowledgePage';
import { ProjectsPage } from '../features/projects/pages/ProjectsPage';
import { DeveloperPage } from '../features/developer/pages/DeveloperPage';
import { PluginsPage } from '../features/plugins/pages/PluginsPage';
import { SettingsPage } from '../features/settings/pages/SettingsPage';

export const router = createBrowserRouter([
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
