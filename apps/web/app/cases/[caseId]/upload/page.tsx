"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAppAuth } from "@/lib/auth";
import { documentCategories, type DocumentCategory } from "@mradi/contracts";
import { ArrowRight, CheckCircle2, FileUp, LockKeyhole, UploadCloud } from "lucide-react";
import { motion } from "framer-motion";
import { AppShell } from "@/components/app-shell";
import { DocumentList, MissingDocumentsWarning } from "@/components/document-list";
import { ProgressTracker } from "@/components/progress-tracker";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { apiFetch, type ApiCase } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ErrorState, LoadingPanel, SuccessState } from "@/components/state-views";

const MAX_UPLOAD_BYTES = Number(process.env.NEXT_PUBLIC_MAX_UPLOAD_BYTES ?? 25_000_000);

export default function UploadDocumentsPage() {
  const params = useParams<{ caseId: string }>();
  const { getToken } = useAppAuth();
  const [landCase, setLandCase] = useState<ApiCase | null>(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [category, setCategory] = useState<DocumentCategory>("title_deed");
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [hasConsent, setHasConsent] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const token = await getToken();
    setLandCase(await apiFetch<ApiCase>(`/cases/${params.caseId}`, token));
    setLoading(false);
  }, [getToken, params.caseId]);

  useEffect(() => {
    void load().catch((err) => {
      setError(err instanceof Error ? err.message : "Unable to load case");
      setLoading(false);
    });
  }, [load]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const file = selectedFile;
    if (!file) {
      setError("Choose a document before uploading.");
      return;
    }
    if (!hasConsent) {
      setError("Confirm consent before uploading this document.");
      return;
    }
    setStatus("Preparing signed upload...");
    setError("");
    setUploadProgress(8);
    try {
      const token = await getToken();
      setUploadProgress(18);
      const sha256 = await hashFile(file);
      setUploadProgress(28);
      const signed = await apiFetch<{ document_id: string; upload_url: string; method: string; headers: Record<string, string> }>(
        "/uploads/signed-url",
        token,
        {
          method: "POST",
          body: JSON.stringify({
            case_id: params.caseId,
            category,
            filename: file.name,
            content_type: file.type || "application/pdf",
            file_size: file.size,
            sha256,
            consent_to_process: hasConsent
          })
        }
      );
      setStatus("Uploading securely...");
      await uploadWithProgress(signed.upload_url, signed.method, signed.headers, file, (progress) => {
        setUploadProgress(30 + Math.round(progress * 0.45));
      });
      setStatus("Scanning and completing upload...");
      setUploadProgress(82);
      await apiFetch("/uploads/complete", token, {
        method: "POST",
        body: JSON.stringify({ document_id: signed.document_id, sha256 })
      });
      setStatus("Upload complete");
      setUploadProgress(100);
      await load();
      setSelectedFile(null);
      setHasConsent(false);
      form.reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setUploadProgress(0);
    }
  }

  function chooseFile(file: File | undefined) {
    if (!file) return;
    const allowed = new Set(["application/pdf", "image/png", "image/jpeg", "image/webp"]);
    if (!allowed.has(file.type)) {
      setError("Upload PDF, PNG, JPG, JPEG, or WEBP files only.");
      setSelectedFile(null);
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setError(`File exceeds the ${formatBytes(MAX_UPLOAD_BYTES)} upload limit.`);
      setSelectedFile(null);
      return;
    }
    setSelectedFile(file);
    setStatus("");
    setError("");
    setUploadProgress(0);
  }

  return (
    <AppShell>
      <ProgressTracker current="documents" />
      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_380px]">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">{landCase?.title ?? "Upload documents"}</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            Documents enter secure quarantine first, then file validation, malware checks, and extraction can run.
          </p>
          {loading ? <div className="mt-6"><LoadingPanel label="Loading document workspace" /></div> : null}
          {!loading && error ? <div className="mt-6"><ErrorState message={error} onRetry={() => void load()} /></div> : null}
          {!loading && !error ? (
            <div className="mt-6 space-y-4">
              <MissingDocumentsWarning documents={landCase?.documents ?? []} />
              <DocumentList documents={landCase?.documents ?? []} />
            </div>
          ) : null}
          <div className="mt-6 flex flex-col gap-3 sm:flex-row">
            <Button asChild>
              <Link href={`/cases/${params.caseId}/extraction`}>Review extraction <ArrowRight className="h-4 w-4" /></Link>
            </Button>
            <Button asChild variant="outline">
              <Link href={`/cases/${params.caseId}/timeline`}>Timeline</Link>
            </Button>
          </div>
        </div>
        <Card className="premium-panel h-fit">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><UploadCloud className="h-5 w-5" aria-hidden="true" /> Upload document</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="space-y-4">
              <div>
                <Label htmlFor="category">Document category</Label>
                <Select id="category" name="category" value={category} onChange={(event) => setCategory(event.target.value as DocumentCategory)}>
                  {documentCategories.map((category) => (
                    <option key={category} value={category}>{category.replaceAll("_", " ")}</option>
                  ))}
                </Select>
              </div>
              <div>
                <Label htmlFor="file">PDF or image</Label>
                <motion.label
                  htmlFor="file"
                  onDragOver={(event) => {
                    event.preventDefault();
                    setIsDragging(true);
                  }}
                  onDragLeave={() => setIsDragging(false)}
                  onDrop={(event) => {
                    event.preventDefault();
                    setIsDragging(false);
                    chooseFile(event.dataTransfer.files[0]);
                  }}
                  whileHover={{ y: -2 }}
                  className={cn(
                    "focus-ring mt-2 flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed p-6 text-center transition-colors",
                    isDragging ? "border-primary bg-primary/10" : "border-border bg-muted/40 hover:bg-muted"
                  )}
                  tabIndex={0}
                >
                  <FileUp className="h-8 w-8 text-primary" aria-hidden="true" />
                  <span className="mt-3 font-medium">{selectedFile ? selectedFile.name : "Drop files here or browse"}</span>
                  <span className="mt-1 text-xs text-muted-foreground">PDF, PNG, JPG, JPEG, or WEBP up to the API upload limit</span>
                </motion.label>
                <Input
                  id="file"
                  name="file"
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg,.webp,application/pdf,image/png,image/jpeg,image/webp"
                  className="sr-only"
                  onChange={(event) => chooseFile(event.target.files?.[0])}
                />
              </div>
              {uploadProgress > 0 ? (
                <div className="space-y-2" aria-live="polite">
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>{status}</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <Progress value={uploadProgress} />
                </div>
              ) : null}
              {status === "Upload complete" ? <SuccessState message="Document uploaded and queued for extraction." /> : null}
              {error ? (
                <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
                  {error}
                </div>
              ) : null}
              <label className="flex items-start gap-3 rounded-md border bg-muted/40 p-3 text-sm leading-5">
                <input
                  className="mt-1 h-4 w-4 shrink-0 accent-primary"
                  type="checkbox"
                  checked={hasConsent}
                  onChange={(event) => setHasConsent(event.target.checked)}
                  required
                />
                <span>
                  I have permission to upload this land transaction document and consent to secure processing for extraction, risk analysis, audit logging, and deletion handling.
                </span>
              </label>
              <Button type="submit" className="w-full" disabled={!selectedFile || !hasConsent || (uploadProgress > 0 && uploadProgress < 100)}>
                <LockKeyhole className="h-4 w-4" aria-hidden="true" />
                Upload securely
              </Button>
              <div className="flex items-start gap-2 rounded-md border bg-muted/40 p-3 text-xs text-muted-foreground">
                <CheckCircle2 className="mt-0.5 h-4 w-4 text-primary" aria-hidden="true" />
                Files use signed upload URLs and are scanned before analysis.
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}

function formatBytes(bytes: number) {
  const megabytes = bytes / 1_000_000;
  return `${megabytes.toFixed(megabytes >= 10 ? 0 : 1)} MB`;
}

async function hashFile(file: File) {
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest)).map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function uploadWithProgress(
  url: string,
  method: string,
  headers: Record<string, string>,
  file: File,
  onProgress: (progress: number) => void
) {
  return new Promise<void>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open(method, url);
    Object.entries(headers).forEach(([key, value]) => request.setRequestHeader(key, value));
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    request.onload = () => {
      if (request.status >= 200 && request.status < 300) resolve();
      else reject(new Error("Signed upload failed"));
    };
    request.onerror = () => reject(new Error("Network error during upload"));
    request.send(file);
  });
}
