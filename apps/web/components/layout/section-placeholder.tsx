import { Badge } from "../ui/badge";
import { Card } from "../ui/card";

interface SectionPlaceholderProps {
  title: string;
  description: string;
}

export function SectionPlaceholder({
  title,
  description,
}: SectionPlaceholderProps) {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Badge variant="neutral">Coming soon</Badge>

        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-text-primary">
          {title}
        </h1>

        <p className="mt-3 max-w-2xl text-base leading-7 text-text-secondary">
          {description}
        </p>
      </div>

      <Card>
        <div className="flex min-h-56 items-center justify-center text-center">
          <div className="max-w-md">
            <p className="text-sm font-medium text-text-primary">
              This workspace is part of the MarketThread product roadmap.
            </p>

            <p className="mt-2 text-sm leading-6 text-text-secondary">
              The shared application shell is ready for the intelligence
              capabilities that will be added in later development phases.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}