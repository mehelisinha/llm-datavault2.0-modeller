import { Sparkles } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle, Icon } from "@/components/ui";

interface PlaceholderCardProps {
  title: string;
  description: string;
  upcomingPhase: string;
}

/**
 * Reusable "coming soon" surface for routes whose real implementation lands
 * in a later sub-phase. Centralising the placeholder avoids five copies of
 * the same JSX in route files.
 */
export function PlaceholderCard({
  title,
  description,
  upcomingPhase,
}: PlaceholderCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon icon={Sparkles} size="md" className="text-primary" />
          {title}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          UI for this step lands in <span className="font-mono">{upcomingPhase}</span>.
        </p>
      </CardContent>
    </Card>
  );
}
