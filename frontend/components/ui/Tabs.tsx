export interface TabItem<T extends string> {
  id: T;
  label: string;
}

export default function Tabs<T extends string>({
  items,
  active,
  onChange,
  size = "md",
}: {
  items: readonly TabItem<T>[];
  active: T;
  onChange: (id: T) => void;
  size?: "sm" | "md";
}) {
  const padding = size === "sm" ? "px-3 py-2" : "px-4 py-2.5";
  return (
    <div className="flex gap-1 border-b border-slate-200">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onChange(item.id)}
          className={`-mb-px border-b-2 text-sm font-medium transition-colors ${padding} ${
            active === item.id
              ? "border-accent text-accent"
              : "border-transparent text-slate-500 hover:text-ink-900"
          }`}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
