// Accessible pill toggle for per-item blueprint selection; a real <button role="switch"> mirroring
// EnvironmentModule's EnvToggleSwitch pattern (native checkboxes can't render the pill/knob visual).
export interface LocalConfigToggleProps {
  checked: boolean;
  label: string;
  disabled?: boolean;
  onToggle: () => void;
}

export function LocalConfigToggle({
  checked,
  label,
  disabled = false,
  onToggle,
}: LocalConfigToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      className={`lcfg-toggle${checked ? " is-on" : ""}`}
      disabled={disabled}
      onClick={onToggle}
    >
      <span className="lcfg-toggle__knob" />
    </button>
  );
}
