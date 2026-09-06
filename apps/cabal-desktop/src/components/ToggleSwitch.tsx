// Shared accessible pill switch matching the Cabal Console control language. Feature modules use
// this instead of carrying slightly different local switch implementations.
export interface ToggleSwitchProps {
  checked: boolean;
  label: string;
  disabled?: boolean;
  onToggle?: () => void;
}

export function ToggleSwitch({ checked, label, disabled = false, onToggle }: ToggleSwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      className={`toggle-switch${checked ? " is-on" : ""}`}
      disabled={disabled || onToggle === undefined}
      onClick={onToggle}
    >
      <span className="toggle-switch__knob" aria-hidden="true" />
    </button>
  );
}
