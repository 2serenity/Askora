import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva("inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium", {
  variants: {
    variant: {
      default: "bg-primary/14 text-primary",
      secondary: "bg-secondary text-secondary-foreground",
      outline: "border border-border bg-black/20 text-foreground",
      success: "bg-primary/14 text-primary",
      warning: "bg-amber-500/14 text-amber-300",
      danger: "bg-rose-500/14 text-rose-300",
    },
  },
  defaultVariants: {
    variant: "default",
  },
});

export function Badge({
  className,
  variant,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof badgeVariants>) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}
