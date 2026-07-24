import { useState, useEffect, useCallback } from 'react';

/**
 * Responsive breakpoint detection hook.
 * Provides mobile/tablet/desktop state and sidebar toggle for mobile.
 *
 * @returns {{ isMobile, isTablet, isDesktop, sidebarOpen, toggleSidebar, closeSidebar, openSidebar }}
 */
export function useResponsive() {
  const [width, setWidth] = useState(window.innerWidth);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    const handleResize = () => setWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Close sidebar when switching from mobile to desktop
  useEffect(() => {
    if (width >= 768 && sidebarOpen) setSidebarOpen(false);
  }, [width, sidebarOpen]);

  const isMobile = width < 768;
  const isTablet = width >= 768 && width < 1024;
  const isDesktop = width >= 1024;

  const toggleSidebar = useCallback(() => setSidebarOpen(prev => !prev), []);
  const closeSidebar = useCallback(() => setSidebarOpen(false), []);
  const openSidebar = useCallback(() => setSidebarOpen(true), []);

  return { isMobile, isTablet, isDesktop, sidebarOpen, toggleSidebar, closeSidebar, openSidebar };
}
