"use client";

import { FormEvent, useState } from "react";
import { Bot, Send, ShieldQuestion } from "lucide-react";
import { useAppAuth } from "@/lib/auth";
import { apiFetch, type ApiCaseAgentAnswer } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";

interface ChatMessage {
  question: string;
  response: ApiCaseAgentAnswer;
}

export function CaseAgentChat({ caseId }: { caseId: string }) {
  const { getToken } = useAppAuth();
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) return;
    setLoading(true);
    setError("");
    try {
      const token = await getToken();
      const response = await apiFetch<ApiCaseAgentAnswer>(`/cases/${caseId}/ask`, token, {
        method: "POST",
        body: JSON.stringify({ question: trimmed })
      });
      setMessages((current) => [{ question: trimmed, response }, ...current].slice(0, 4));
      setQuestion("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to ask the case agent");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="premium-panel">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-primary" aria-hidden="true" />
          Ask the agent
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={onSubmit} className="space-y-3">
          <Textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask about seller-owner match, missing search, Gazette findings, parcel mismatch, or next steps..."
            rows={3}
          />
          {error ? <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">{error}</div> : null}
          <Button className="w-full" disabled={loading || question.trim().length < 3}>
            <Send className="h-4 w-4" aria-hidden="true" />
            {loading ? "Checking evidence..." : "Ask using case evidence"}
          </Button>
        </form>

        <div className="flex items-start gap-2 rounded-md border bg-muted/40 p-3 text-xs leading-5 text-muted-foreground">
          <ShieldQuestion className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
          Answers are limited to uploaded documents, extracted fields, Gazette results, verification attempts, and risk analysis.
        </div>

        {messages.length ? (
          <div className="space-y-3">
            {messages.map((message, index) => (
              <article key={`${message.question}-${index}`} className="rounded-lg border bg-background/70 p-3">
                <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">You asked</div>
                <p className="mt-1 text-sm font-medium">{message.question}</p>
                <div className="mt-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">Answer</div>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">{message.response.answer}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Badge variant="outline">{message.response.verification_status.replaceAll("_", " ")}</Badge>
                  <Badge variant="secondary">{message.response.citations.length} citations</Badge>
                </div>
                {message.response.citations.length ? (
                  <div className="mt-3 space-y-2">
                    {message.response.citations.slice(0, 3).map((citation, citationIndex) => (
                      <div key={`${citation.title}-${citationIndex}`} className="rounded-md border bg-muted/30 p-2 text-xs leading-5 text-muted-foreground">
                        <div className="font-medium text-foreground">{citation.title}</div>
                        <div className="mt-1 line-clamp-3">{citation.excerpt}</div>
                        {citation.confidence !== null ? <div className="mt-1">{Math.round(citation.confidence * 100)}% confidence</div> : null}
                      </div>
                    ))}
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
