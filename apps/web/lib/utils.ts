import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(value?: string) {
  if (!value) return "Not recorded";
  return new Intl.DateTimeFormat("en-KE", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}

export function riskColor(score: number) {
  if (score <= 30) return "text-emerald-600";
  if (score <= 60) return "text-amber-600";
  if (score <= 80) return "text-orange-600";
  return "text-red-600";
}
