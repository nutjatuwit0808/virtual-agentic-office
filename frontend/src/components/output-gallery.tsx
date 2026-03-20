"use client";

import { useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import type { Components } from "react-markdown";
import { Download, Loader2 } from "lucide-react";

import { getApiBaseUrl } from "@/lib/env";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

type PreviewKind = "markdown" | "code" | "image" | "text";

export type GalleryOutputItem = {
  id: string;
  topic: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  preview: {
    kind: PreviewKind;
    excerpt?: string;
    language?: string;
  };
  created_at: string;
  file_url: string;
};

const markdownComponents: Components = {
  code(props) {
    const { children, className, ...rest } = props;
    const text = String(children);
    const match = /language-(\w+)/.exec(className ?? "");
    const isBlock = match || text.includes("\n");
    if (!isBlock) {
      return (
        <code
          className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]"
          {...rest}
        >
          {children}
        </code>
      );
    }
    const language = match ? match[1] : "text";
    return (
      <SyntaxHighlighter
        language={language}
        style={oneDark}
        PreTag="div"
        className="!my-2 !rounded-lg !text-xs"
      >
        {text.replace(/\n$/, "")}
      </SyntaxHighlighter>
    );
  },
};

function PreviewBody({
  item,
  textContent,
}: {
  item: GalleryOutputItem;
  textContent: string | null;
}) {
  const kind = item.preview.kind;

  if (kind === "image") {
    const src = `${getApiBaseUrl()}${item.file_url}`;
    return (
      <div className="flex justify-center overflow-hidden rounded-md border bg-muted/30 p-2">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt={item.filename}
          className="max-h-[240px] max-w-full object-contain"
        />
      </div>
    );
  }

  if (textContent === null) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />
        <span className="text-xs">Loading preview…</span>
      </div>
    );
  }

  if (kind === "markdown") {
    return (
      <ScrollArea className="h-[220px] rounded-md border bg-muted/20 p-3">
        <div className="space-y-2 text-sm leading-relaxed text-foreground [&_h1]:text-base [&_h1]:font-semibold [&_h2]:text-sm [&_h2]:font-semibold [&_h3]:text-sm [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_a]:text-primary [&_a]:underline [&_blockquote]:border-l-2 [&_blockquote]:border-muted-foreground/30 [&_blockquote]:pl-3 [&_blockquote]:italic">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={markdownComponents}
          >
            {textContent}
          </ReactMarkdown>
        </div>
      </ScrollArea>
    );
  }

  if (kind === "code") {
    const lang = item.preview.language ?? "text";
    return (
      <ScrollArea className="h-[220px] rounded-md border">
        <SyntaxHighlighter
          language={lang}
          style={oneDark}
          customStyle={{ margin: 0, borderRadius: "0.375rem", fontSize: "0.75rem" }}
          PreTag="div"
        >
          {textContent}
        </SyntaxHighlighter>
      </ScrollArea>
    );
  }

  return (
    <ScrollArea className="h-[180px] rounded-md border bg-muted/20 p-3">
      <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">
        {textContent}
      </pre>
    </ScrollArea>
  );
}

export function OutputGallery({ refreshKey }: { refreshKey: number }) {
  const [items, setItems] = useState<GalleryOutputItem[]>([]);
  const [textById, setTextById] = useState<Record<string, string | null>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const base = getApiBaseUrl();
      const res = await fetch(`${base}/api/outputs`);
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as { items: GalleryOutputItem[] };
      setItems(data.items);
      setTextById({});

      const next: Record<string, string | null> = {};
      await Promise.all(
        data.items.map(async (item) => {
          if (item.preview.kind === "image") {
            return;
          }
          next[item.id] = null;
          try {
            const fr = await fetch(`${base}${item.file_url}`);
            if (!fr.ok) throw new Error("fetch failed");
            next[item.id] = await fr.text();
          } catch {
            next[item.id] = item.preview.excerpt ?? "(Could not load file)";
          }
        })
      );
      setTextById(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load outputs");
      setItems([]);
      setTextById({});
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  return (
    <Card className="border shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Output gallery</CardTitle>
        <CardDescription>
          Writer outputs saved under server storage — markdown, code, and images.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            <span className="text-sm">Loading…</span>
          </div>
        )}
        {error && (
          <p className="text-sm text-destructive">{error}</p>
        )}
        {!loading && !error && items.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No outputs yet. Run the research → write workflow to create one.
          </p>
        )}
        {!loading && items.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
            {items.map((item) => (
              <Card
                key={item.id}
                size="sm"
                className="ring-foreground/10"
              >
                <CardHeader className="border-b pb-3">
                  <CardTitle className="line-clamp-2 text-sm font-medium">
                    {item.topic}
                  </CardTitle>
                  <CardDescription className="text-xs">
                    {item.filename} · {(item.size_bytes / 1024).toFixed(1)} KB ·{" "}
                    <span className="capitalize">{item.preview.kind}</span>
                  </CardDescription>
                </CardHeader>
                <CardContent className="pt-3">
                  <PreviewBody
                    item={item}
                    textContent={
                      item.preview.kind === "image"
                        ? ""
                        : (textById[item.id] ?? null)
                    }
                  />
                </CardContent>
                <CardFooter className="justify-end gap-2 border-t bg-muted/30 py-2">
                  <a
                    href={`${getApiBaseUrl()}${item.file_url}?download=true`}
                    download={item.filename}
                    className={cn(
                      buttonVariants({ variant: "outline", size: "sm" }),
                      "h-8 gap-1.5"
                    )}
                  >
                    <Download className="size-3.5" />
                    Download
                  </a>
                </CardFooter>
              </Card>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
