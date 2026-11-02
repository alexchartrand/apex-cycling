import { apiRequest } from "./client";

/** Fetches `path` and saves the response through the browser, named by its
 *  Content-Disposition (else `fallbackName`). */
export async function downloadFile(path: string, fallbackName: string): Promise<void> {
  const response = await apiRequest(path);
  const filename = /filename="([^"]+)"/.exec(response.headers.get("Content-Disposition") ?? "")?.[1] ?? fallbackName;
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
