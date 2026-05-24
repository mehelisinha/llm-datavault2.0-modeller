/**
 * Browser file-download helper.
 *
 * Appends a temporary `<a>` element to the DOM before clicking so all
 * browsers honour the `download` attribute (Safari blocks downloads from
 * detached anchors). The object URL is revoked after a short delay so the
 * browser has time to start the download.
 */
export function downloadTextFile(
  content: string,
  filename: string,
  mimeType = "text/plain;charset=utf-8",
): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  window.setTimeout(() => URL.revokeObjectURL(url), 200);
}

export const YAML_MIME = "text/yaml;charset=utf-8";
