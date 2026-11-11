import { GeistSans } from "geist/font/sans";
import TopNav from "@/components/TopNav";
import "./globals.css";

export const metadata = {
  title: { default: "Job Assist", template: "%s | Job Assist" },
  description: "Find Greenhouse jobs that fit you and prepare your applications.",
};

export default function RootLayout({ children }) {
  // Filled in from the login session once sign-in is added: { name, email, picture }.
  const user = null;

  return (
    <html lang="en" className={`${GeistSans.variable} h-full antialiased`}>
      <body className="min-h-full bg-paper text-ink">
        <TopNav user={user} />
        <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">{children}</main>
      </body>
    </html>
  );
}