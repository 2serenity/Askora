"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";

const schema = z.object({
  email: z.string().email("Введите корректный email"),
  password: z.string().min(6, "Минимум 6 символов"),
});

type FormValues = z.infer<typeof schema>;

export function LoginForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      email: "business@demo.local",
      password: "DemoBusiness123",
    },
  });

  const mutation = useMutation({
    mutationFn: api.login,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      router.push("/workspace");
    },
  });

  return (
    <Card className="border-primary/14 bg-black/52">
      <CardHeader>
        <CardTitle className="text-2xl">Вход в рабочее пространство</CardTitle>
        <CardDescription>
          Реальный вход с ролями «Администратор», «Аналитик» и «Пользователь». Для демо уже подготовлены тестовые аккаунты.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <form className="space-y-4" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" {...form.register("email")} />
            {form.formState.errors.email && <p className="text-sm text-rose-300">{form.formState.errors.email.message}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Пароль</Label>
            <Input id="password" type="password" {...form.register("password")} />
            {form.formState.errors.password && <p className="text-sm text-rose-300">{form.formState.errors.password.message}</p>}
          </div>
          {mutation.error instanceof ApiError && (
            <p className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{mutation.error.message}</p>
          )}
          <Button className="w-full" size="lg" disabled={mutation.isPending}>
            {mutation.isPending ? "Входим..." : "Войти"}
          </Button>
        </form>
        <div className="rounded-2xl border border-border/80 bg-black/24 p-4 text-sm text-muted-foreground">
          <div className="mb-2 font-medium text-foreground">Демо-аккаунты</div>
          <div><code>admin@demo.local</code> / <code>DemoAdmin123</code></div>
          <div><code>analyst@demo.local</code> / <code>DemoAnalyst123</code></div>
          <div><code>business@demo.local</code> / <code>DemoBusiness123</code></div>
        </div>
      </CardContent>
    </Card>
  );
}
