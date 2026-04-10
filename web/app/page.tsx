import Chat from "@/components/Chat";

export default function Home() {
  return (
    <div className="relative min-h-full bg-surface bg-grid">
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-accent/10 via-transparent to-transparent" />
      <Chat />
    </div>
  );
}
