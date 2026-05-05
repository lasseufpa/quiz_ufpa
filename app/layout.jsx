import './globals.css';
import 'katex/dist/katex.min.css';
import { Manrope, Space_Grotesk } from 'next/font/google';

const bodyFont = Manrope({
  subsets: ['latin'],
  variable: '--font-body'
});

const headingFont = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-heading'
});

export const metadata = {
  title: 'Quiz UFPA',
  description: 'Plataforma interativa de quizzes com Node.js e Next.js'
};

export default function RootLayout({ children }) {
  return (
    <html lang="pt-br">
      <body className={`${bodyFont.variable} ${headingFont.variable}`}>
        <div className="page-shell">
          <header className="topbar">
            <a href="/" className="brand">Quiz UFPA</a>
            <nav className="topnav">
              <a href="/host">Host</a>
              <a href="/editor">Editor</a>
              <a href="/admin/login">Admin</a>
            </nav>
          </header>
          <main className="page-main">{children}</main>
        </div>
      </body>
    </html>
  );
}