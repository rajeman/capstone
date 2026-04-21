import { ClerkProvider } from '@clerk/nextjs';
import type { AppProps } from 'next/app';
import { ClerkBackendSync } from '../components/ClerkBackendSync';
import '../styles/globals.css';

export default function MyApp({ Component, pageProps }: AppProps) {
  return (
    <ClerkProvider {...pageProps}>
      <ClerkBackendSync />
      <Component {...pageProps} />
    </ClerkProvider>
  );
}