import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";


export type SelectMenuOption = {
  value: string;
  label: string;
};

export function SelectMenu({
  label,
  value,
  options,
  onChange,
  disabled = false,
}: {
  label: string;
  value: string;
  options: SelectMenuOption[];
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const selectedIndex = options.findIndex((option) => option.value === value);
  const [activeIndex, setActiveIndex] = useState(Math.max(0, selectedIndex));
  const rootRef = useRef<HTMLDivElement>(null);
  const typeaheadRef = useRef("");
  const typeaheadTimerRef = useRef<number | undefined>(undefined);
  const listboxId = useId();

  useEffect(() => {
    if (!open) return;
    const closeOutside = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", closeOutside);
    return () => document.removeEventListener("pointerdown", closeOutside);
  }, [open]);

  useEffect(() => () => window.clearTimeout(typeaheadTimerRef.current), []);

  function showMenu() {
    if (disabled || !options.length) return;
    setActiveIndex(selectedIndex >= 0 ? selectedIndex : 0);
    setOpen(true);
  }

  function choose(index: number) {
    const option = options[index];
    if (!option) return;
    onChange(option.value);
    setActiveIndex(index);
    setOpen(false);
  }

  function moveActive(direction: 1 | -1) {
    setActiveIndex((current) => {
      const next = current + direction;
      if (next < 0) return options.length - 1;
      if (next >= options.length) return 0;
      return next;
    });
  }

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) showMenu();
      else moveActive(event.key === "ArrowDown" ? 1 : -1);
      return;
    }
    if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      if (!open) showMenu();
      setActiveIndex(event.key === "Home" ? 0 : options.length - 1);
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (open) choose(activeIndex);
      else showMenu();
      return;
    }
    if (event.key === "Escape" && open) {
      event.preventDefault();
      setOpen(false);
      return;
    }
    if (event.key === "Tab") {
      setOpen(false);
      return;
    }
    if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      typeaheadRef.current += event.key.toLocaleLowerCase();
      window.clearTimeout(typeaheadTimerRef.current);
      typeaheadTimerRef.current = window.setTimeout(() => { typeaheadRef.current = ""; }, 500);
      const match = options.findIndex((option) => option.label.toLocaleLowerCase().startsWith(typeaheadRef.current));
      if (match >= 0) {
        event.preventDefault();
        if (!open) showMenu();
        setActiveIndex(match);
      }
    }
  }

  const selected = options[selectedIndex];
  const activeOptionId = open && options[activeIndex] ? `${listboxId}-option-${activeIndex}` : undefined;

  return (
    <div className="select-field">
      <span className="select-field__label">{label}</span>
      <div className={`select-menu${open ? " is-open" : ""}`} ref={rootRef}>
        <button
          type="button"
          className="select-menu__trigger"
          role="combobox"
          aria-label={label}
          aria-controls={listboxId}
          aria-expanded={open}
          aria-activedescendant={activeOptionId}
          disabled={disabled || !options.length}
          onClick={() => open ? setOpen(false) : showMenu()}
          onKeyDown={handleKeyDown}
        >
          <span>{selected?.label ?? value}</span>
          <span className="select-menu__chevron" aria-hidden="true" />
        </button>
        {open && (
          <div className="select-menu__list" id={listboxId} role="listbox" aria-label={label}>
            {options.map((option, index) => (
              <div
                id={`${listboxId}-option-${index}`}
                className={`select-menu__option${index === activeIndex ? " is-active" : ""}${option.value === value ? " is-selected" : ""}`}
                key={option.value}
                role="option"
                aria-selected={option.value === value}
                onClick={() => choose(index)}
                onMouseDown={(event) => event.preventDefault()}
                onPointerMove={() => setActiveIndex(index)}
              >
                <span className="select-menu__mark" aria-hidden="true" />
                <span>{option.label}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
