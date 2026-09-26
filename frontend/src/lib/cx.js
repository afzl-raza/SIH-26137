// Tiny classname joiner - avoids adding a `clsx`/`classnames` dependency
// for what is just filtering falsy values out of a class list.
export function cx(...parts) {
  return parts.filter(Boolean).join(' ');
}
