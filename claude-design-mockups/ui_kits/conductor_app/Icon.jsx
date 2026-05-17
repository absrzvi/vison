// Icon — uses the inline window.OBB_ICONS map.
// Usage: <Icon name="alert-triangle" size={16} color="#FF6B00" stroke={2.5} />

function Icon(props) {
  const name = props.name;
  const size = props.size ?? 18;
  const color = props.color ?? "currentColor";
  const stroke = props.stroke ?? 2;
  const style = props.style || {};

  const def = window.OBB_ICONS[name];
  if (!def) {
    return <span style={{ display: "inline-block", width: size, height: size, ...style }} title={`missing icon: ${name}`} />;
  }
  return (
    <svg
      width={size} height={size}
      viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth={stroke}
      strokeLinecap="round" strokeLinejoin="round"
      style={{ display: "inline-block", flexShrink: 0, verticalAlign: "middle", ...style }}
    >
      {def.map(function (entry, i) {
        const tag = entry[0];
        const attrs = entry[1];
        return React.createElement(tag, Object.assign({ key: i }, attrs));
      })}
    </svg>
  );
}

window.Icon = Icon;
