'use client';

import React from 'react';

interface StatCardProps {
    label: string;
    value: string | number;
    subtext?: string;
    icon?: React.ReactNode;
    emoji?: string;
    trend?: {
        value: number;
        direction: 'up' | 'down' | 'neutral';
    };
    color?: 'indigo' | 'emerald' | 'amber' | 'rose' | 'blue' | 'purple' | 'slate';
    onClick?: () => void;
    className?: string;
}

const colorMap = {
    indigo: 'from-indigo-500 to-purple-500',
    emerald: 'from-emerald-500 to-teal-500',
    amber: 'from-amber-500 to-orange-500',
    rose: 'from-rose-500 to-red-500',
    blue: 'from-blue-500 to-indigo-500',
    purple: 'from-purple-500 to-pink-500',
    slate: 'from-slate-500 to-slate-600'
};

export function StatCard({
    label,
    value,
    subtext,
    icon,
    emoji,
    trend,
    color = 'indigo',
    onClick,
    className = ''
}: StatCardProps) {
    const Component = onClick ? 'button' : 'div';

    return (
        <Component
            onClick={onClick}
            className={`
        relative overflow-hidden bg-white/5 border border-white/10 rounded-2xl p-5 text-left
        hover:bg-white/[0.07] transition-all group
        ${onClick ? 'cursor-pointer' : ''}
        ${className}
      `}
        >
            <div className="flex items-start justify-between">
                <div>
                    <p className="text-slate-400 text-sm font-medium">{label}</p>
                    <div className="flex items-baseline gap-2 mt-1">
                        <p className="text-3xl font-bold text-white">{value}</p>
                        {trend && (
                            <span className={`
                text-xs font-semibold flex items-center gap-0.5
                ${trend.direction === 'up' ? 'text-emerald-400' : ''}
                ${trend.direction === 'down' ? 'text-red-400' : ''}
                ${trend.direction === 'neutral' ? 'text-slate-400' : ''}
              `}>
                                {trend.direction === 'up' && '↑'}
                                {trend.direction === 'down' && '↓'}
                                {trend.value}%
                            </span>
                        )}
                    </div>
                    {subtext && <p className="text-slate-500 text-xs mt-1">{subtext}</p>}
                </div>

                {(icon || emoji) && (
                    <div className={`
            w-10 h-10 rounded-xl bg-gradient-to-br ${colorMap[color]} 
            flex items-center justify-center text-lg
            group-hover:scale-110 transition-transform
          `}>
                        {emoji || icon}
                    </div>
                )}
            </div>

            {/* Bottom gradient accent */}
            <div className={`absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r ${colorMap[color]} opacity-50`} />
        </Component>
    );
}

// Compact variant for smaller spaces
export function StatCardCompact({
    label,
    value,
    icon,
    color = 'indigo'
}: Pick<StatCardProps, 'label' | 'value' | 'icon' | 'color'>) {
    return (
        <div className="flex items-center gap-3 p-3 bg-white/5 border border-white/10 rounded-xl">
            <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${colorMap[color || 'indigo']} flex items-center justify-center`}>
                {icon}
            </div>
            <div>
                <p className="text-lg font-bold text-white">{value}</p>
                <p className="text-xs text-slate-400">{label}</p>
            </div>
        </div>
    );
}

export default StatCard;
