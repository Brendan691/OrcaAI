import { Badge } from "@/components/ui/badge";
import { DocTags, flattenTags } from "@/lib/api";

/** 展示一个文档的标签(四维汇总为一排 chip)。 */
export function TagList({ tags, max = 12 }: { tags?: DocTags; max?: number }) {
  const all = flattenTags(tags);
  if (all.length === 0) {
    return <span className="text-xs text-muted-foreground">无标签</span>;
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {all.slice(0, max).map((t, i) => (
        <Badge key={`${t}-${i}`} variant="secondary" className="font-normal">
          {t}
        </Badge>
      ))}
    </div>
  );
}
