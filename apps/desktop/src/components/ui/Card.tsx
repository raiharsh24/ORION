import React, { forwardRef } from 'react';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'glow' | 'flat';
  hoverable?: boolean;
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className = '', variant = 'default', hoverable = false, children, ...props }, ref) => {
    const baseStyles = 'rounded-2xl border transition-all duration-300 relative overflow-hidden';
    
    const variants = {
      default: 'bg-matte-card/65 border-matte-border backdrop-blur-md',
      glow: 'bg-matte-card/80 border-cyan-border/30 shadow-[0_0_20px_rgba(0,242,254,0.03)] focus:border-cyan-glow/50 hover:shadow-[0_0_30px_rgba(0,242,254,0.06)]',
      flat: 'bg-zinc-950/40 border-matte-border',
    };

    const hoverStyles = hoverable 
      ? 'hover:-translate-y-0.5 hover:border-cyan-border/40 hover:bg-matte-card/85 cursor-pointer' 
      : '';

    return (
      <div
        ref={ref}
        className={`${baseStyles} ${variants[variant]} ${hoverStyles} ${className}`}
        {...props}
      >
        {/* Subtle decorative grid/glow inside card for premium aesthetic */}
        {variant === 'glow' && (
          <div className="absolute top-0 left-0 w-8 h-[1px] bg-gradient-to-r from-transparent via-cyan-glow/40 to-transparent" />
        )}
        <div className="relative z-10 w-full h-full">
          {children}
        </div>
      </div>
    );
  }
);
Card.displayName = 'Card';

export const CardHeader = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className = '', ...props }, ref) => (
    <div ref={ref} className={`p-6 pb-4 flex flex-col gap-1.5 ${className}`} {...props} />
  )
);
CardHeader.displayName = 'CardHeader';

export const CardTitle = forwardRef<HTMLHeadingElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className = '', children, ...props }, ref) => (
    <h3 ref={ref} className={`text-lg font-bold text-zinc-100 tracking-tight leading-none ${className}`} {...props}>
      {children}
    </h3>
  )
);
CardTitle.displayName = 'CardTitle';

export const CardDescription = forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(
  ({ className = '', ...props }, ref) => (
    <p ref={ref} className={`text-xs font-mono text-zinc-400 ${className}`} {...props} />
  )
);
CardDescription.displayName = 'CardDescription';

export const CardContent = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className = '', ...props }, ref) => (
    <div ref={ref} className={`p-6 pt-0 text-sm text-zinc-300 leading-relaxed ${className}`} {...props} />
  )
);
CardContent.displayName = 'CardContent';

export const CardFooter = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className = '', ...props }, ref) => (
    <div ref={ref} className={`p-6 pt-0 flex items-center border-t border-matte-border/30 mt-auto ${className}`} {...props} />
  )
);
CardFooter.displayName = 'CardFooter';
