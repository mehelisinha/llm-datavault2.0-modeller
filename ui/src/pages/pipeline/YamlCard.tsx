/**
 * YAML preview + download. The YAML lives on `PipelineRun.rendered_yaml`
 * once the `generate` step has succeeded.
 */
import { Button, Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui";
import { PIPELINE_LABELS, type PipelineRun } from "@/constants/pipeline";
import { downloadTextFile, YAML_MIME } from "@/lib/download";

export function YamlCard({ run }: { run: PipelineRun }) {
  const yaml = run.rendered_yaml ?? "";
  if (!yaml) return null;
  const systemId = run.system?.system_id ?? run.plan?.system_id ?? "metadata";

  const handleDownload = () => {
    downloadTextFile(yaml, PIPELINE_LABELS.downloadFilename(systemId), YAML_MIME);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {PIPELINE_LABELS.sectionYaml}{" "}
          <span className="text-xs font-normal text-muted-foreground">
            ({yaml.split("\n").length} lines)
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <pre className="max-h-96 overflow-auto rounded bg-muted p-3 text-xs">
          <code>{yaml}</code>
        </pre>
      </CardContent>
      <CardFooter className="justify-end border-t pt-4">
        <Button onClick={handleDownload}>{PIPELINE_LABELS.downloadButton}</Button>
      </CardFooter>
    </Card>
  );
}
