import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function SettingsPage() {
  return (
    <div className="flex flex-1 flex-col gap-6 p-4 md:p-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Workspace preferences will live here.
        </p>
      </div>
      <Card className="max-w-lg">
        <CardHeader>
          <CardTitle>Coming soon</CardTitle>
          <CardDescription>
            Configure API keys, model selection, and office layout presets.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          This placeholder keeps the sidebar navigation complete.
        </CardContent>
      </Card>
    </div>
  );
}
