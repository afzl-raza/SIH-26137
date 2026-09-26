import React from 'react';
import { cx } from '../../lib/cx';

export default function Spinner({ size = 16, className = '' }) {
  return (
    <div
      className={cx('border-2 border-[#C6602E] border-t-transparent rounded-full animate-spin flex-shrink-0', className)}
      style={{ width: size, height: size }}
    />
  );
}
