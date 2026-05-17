function Icon(props) {
  const name = props.name;
  const size = props.size ?? 18;
  const color = props.color ?? "currentColor";
  const stroke = props.stroke ?? 2;
  const style = props.style || {};

  const def = window.OBB_ICONS[name];
  if (!def) return <span style={{ display: "inline-block", width: size, height: size, ...style }} title={`missing icon: ${name}`} />;

  return (
    <svg
      width={size} height={size}
      viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth={stroke}
      strokeLinecap="round" strokeLinejoin="round"
      style={{ display: "inline-block", flexShrink: 0, verticalAlign: "middle", ...style }}>
      {def.map(function (entry, i) {
        return React.createElement(entry[0], Object.assign({ key: i }, entry[1]));
      })}
    </svg>
  );
}
window.Icon = Icon;
