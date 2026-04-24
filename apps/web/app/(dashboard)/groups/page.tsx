import { GroupWorkspace } from "@/components/groups/group-workspace";

export default function GroupsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Рабочие группы</h1>
        <p className="mt-2 text-muted-foreground">
          Внутренние команды для обсуждения отчётов, распределения доступа и совместной работы внутри платформы.
        </p>
      </div>
      <GroupWorkspace />
    </div>
  );
}
