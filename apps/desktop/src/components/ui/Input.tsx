import React, { forwardRef } from 'react';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  icon?: React.ReactNode;
  suffixIcon?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className = '', label, error, helperText, icon, suffixIcon, type = 'text', disabled, ...props }, ref) => {
    const isError = !!error;

    return (
      <div className="w-full flex flex-col gap-1.5 items-start">
        {label && (
          <label className="text-xs font-semibold tracking-wider text-zinc-400 uppercase font-mono">
            {label}
          </label>
        )}

        <div className="w-full relative flex items-center">
          {icon && (
            <div className="absolute left-3.5 flex items-center pointer-events-none text-zinc-500">
              {icon}
            </div>
          )}

          <input
            ref={ref}
            type={type}
            disabled={disabled}
            aria-invalid={isError ? 'true' : 'false'}
            className={`
              w-full bg-black/40 border rounded-xl py-2.5 px-4 text-sm font-mono text-zinc-200 
              placeholder-zinc-600 focus:outline-none transition-all duration-200
              disabled:opacity-50 disabled:cursor-not-allowed
              ${icon ? 'pl-10' : ''} 
              ${suffixIcon ? 'pr-10' : ''}
              ${isError 
                ? 'border-rose-500/50 focus:border-rose-500 focus:ring-1 focus:ring-rose-500/40' 
                : 'border-matte-border hover:border-cyan-border/40 focus:border-cyan-glow focus:ring-1 focus:ring-cyan-glow/40'}
              ${className}
            `}
            {...props}
          />

          {suffixIcon && (
            <div className="absolute right-3.5 flex items-center pointer-events-none text-zinc-500">
              {suffixIcon}
            </div>
          )}
        </div>

        {isError && (
          <span className="text-[11px] font-mono text-rose-400">
            {error}
          </span>
        )}

        {!isError && helperText && (
          <span className="text-[10px] font-mono text-zinc-500">
            {helperText}
          </span>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
