export default function PageHeader({ title, description }) {
  return (
    <header className="mb-8">
      <h1 className="text-3xl font-bold tracking-tight">{title}</h1>
      {description && <p className="mt-2 text-muted">{description}</p>}
    </header>
  );
}
