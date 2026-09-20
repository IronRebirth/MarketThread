import { authenticatedFetch } from "./auth-api";

export type ResearchCitation = {
  reference_id: string;
  source_type: string;
  source_record_id: string;
  observed_at: string;
  title: string | null;
  url: string | null;
};

export type ResearchAnswer = {
  question: string;
  as_of: string;
  answer: string;
  key_points: string[];
  explanation: string;
  uncertainty: string[];
  citations: ResearchCitation[];
  model: string;
  generated_at: string;
  grounded: boolean;
};

export class ResearchAssistantApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ResearchAssistantApiError";
    this.status = status;
  }
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

async function readErrorMessage(response: Response): Promise<string> {
  const detail = await response.text();

  if (!detail) {
    return `Research request failed (${response.status})`;
  }

  try {
    const payload = JSON.parse(detail) as {
      detail?: unknown;
    };

    if (typeof payload.detail === "string") {
      return payload.detail;
    }

    if (
      Array.isArray(payload.detail) &&
      payload.detail.every(
        (item) =>
          typeof item === "object" &&
          item !== null &&
          "msg" in item &&
          typeof item.msg === "string",
      )
    ) {
      return payload.detail.map((item) => item.msg).join(" ");
    }
  } catch {
    // Fall back to the raw response body.
  }

  return detail;
}

export async function askResearchAssistant(
  question: string,
  asOf?: string,
  limit = 8,
): Promise<ResearchAnswer> {
  const normalizedQuestion = question.trim();

  if (!normalizedQuestion) {
    throw new ResearchAssistantApiError(
      422,
      "Enter a research question.",
    );
  }

  const response = await authenticatedFetch(
    `${API_BASE_URL}/research/answer`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question: normalizedQuestion,
        ...(asOf ? { as_of: asOf } : {}),
        limit,
      }),
    },
  );

  if (!response.ok) {
    throw new ResearchAssistantApiError(
      response.status,
      await readErrorMessage(response),
    );
  }

  return (await response.json()) as ResearchAnswer;
}
