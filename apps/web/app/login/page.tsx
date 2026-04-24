import { LoginForm } from "@/components/auth/login-form";

export default function LoginPage() {
  return (
    <main className="page-shell min-h-screen px-6 py-10">
      <div className="mx-auto grid min-h-[calc(100vh-5rem)] max-w-7xl items-center gap-8 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="space-y-6">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="flex flex-col items-center text-center md:col-start-2">
              <img src="/askora-logo.svg" alt="Askora" className="h-36 w-36 md:h-44 md:w-44" />
              <div className="space-y-4">
                <h1 className="max-w-3xl font-[var(--font-display)] text-5xl font-semibold leading-tight md:text-6xl">
                  Askora
                </h1>
                <div aria-hidden="true" className="max-w-2xl h-[84px]" />
              </div>
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {[
              "Работа на реальном датасете заказов и тендеров",
              "Роли, аудит действий и защита SQL",
              "История запросов, отчёты и планирование запусков",
            ].map((item) => (
              <div key={item} className="rounded-2xl border border-border/80 bg-black/35 p-4 text-sm text-muted-foreground">
                {item}
              </div>
            ))}
          </div>
        </section>
        <LoginForm />
      </div>
    </main>
  );
}
