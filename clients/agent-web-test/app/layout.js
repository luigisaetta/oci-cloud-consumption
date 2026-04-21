import "./globals.css";

export const metadata = {
  title: "OCI Consumption Agent Test Client",
  description: "Simple Next.js client to test tool-calling agent API",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
