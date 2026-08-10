// Accessible pill toggle used for the environment table's ON column; a real <button role="switch">
// since native checkboxes cannot render the pill/knob visual — stays keyboard operable via Enter/Space.
export interface EnvToggleSwitchProps {
  checked: boolean;
  label: string;
  disabled?: boolean;
  onToggle?: () => void;
}

export function EnvToggleSwitch({ checked, label, disabled = false, onToggle }: EnvToggleSwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      className={`env-toggle${checked ? " is-on" : ""}`}
      disabled={disabled || onToggle === undefined}
      onClick={onToggle}
    >
      <span className="env-toggle__knob" />
    </button>
  );
}
