import { Fragment, useMemo } from "react";
import { parseMarkdown, type Inline } from "./markdown";

function Inlines({ content }: { content: Inline[] }) {
  return (
    <>
      {content.map((part, index) => {
        if (part.type === "strong") return <strong key={index}>{part.text}</strong>;
        if (part.type === "em") return <em key={index}>{part.text}</em>;
        if (part.type === "code") return <code key={index}>{part.text}</code>;
        return <Fragment key={index}>{part.text}</Fragment>;
      })}
    </>
  );
}

/** The AI coach's text, rendered from Markdown as React elements (no HTML). */
export function Markdown({ text, className }: { text: string; className?: string }) {
  const blocks = useMemo(() => parseMarkdown(text), [text]);
  return (
    <div className={["ai-markdown", className].filter(Boolean).join(" ")}>
      {blocks.map((block, index) => {
        switch (block.type) {
          case "heading": {
            const Tag = (["h3", "h4", "h5"] as const)[block.level - 1];
            return (
              <Tag key={index}>
                <Inlines content={block.content} />
              </Tag>
            );
          }
          case "quote":
            return (
              <blockquote key={index}>
                <Inlines content={block.content} />
              </blockquote>
            );
          case "list": {
            const Tag = block.ordered ? "ol" : "ul";
            return (
              <Tag key={index}>
                {block.items.map((item, i) => (
                  <li key={i}>
                    <Inlines content={item} />
                  </li>
                ))}
              </Tag>
            );
          }
          default:
            return (
              <p key={index}>
                <Inlines content={block.content} />
              </p>
            );
        }
      })}
    </div>
  );
}
