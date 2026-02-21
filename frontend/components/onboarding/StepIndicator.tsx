'use client';

import { motion } from 'framer-motion';

interface StepIndicatorProps {
  currentStep: number;
  totalSteps: number;
  stepTitles: string[];
}

export function StepIndicator({ currentStep, totalSteps, stepTitles }: StepIndicatorProps) {
  return (
    <div className="w-full">
      {/* Progress bar */}
      <div className="relative h-2 bg-slate-800 rounded-full overflow-hidden mb-6">
        <motion.div
          className="absolute top-0 left-0 h-full bg-indigo-600"
          initial={{ width: 0 }}
          animate={{ width: `${(currentStep / totalSteps) * 100}%` }}
          transition={{ duration: 0.3, ease: 'easeInOut' }}
        />
      </div>

      {/* Step circles */}
      <div className="flex items-center justify-between">
        {Array.from({ length: totalSteps }, (_, i) => i + 1).map((step) => {
          const isCompleted = step < currentStep;
          const isCurrent = step === currentStep;

          return (
            <div key={step} className="flex flex-col items-center flex-1">
              <motion.div
                initial={false}
                animate={{ scale: isCurrent ? 1.1 : 1 }}
                className={`
                  w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold
                  transition-colors duration-200 border-2
                  ${
                    isCompleted || isCurrent
                      ? 'bg-indigo-600 text-white border-indigo-600'
                      : 'bg-slate-800 text-slate-400 border-slate-700'
                  }
                `}
              >
                {isCompleted ? (
                  <span>✓</span>
                ) : (
                  step
                )}
              </motion.div>
              <span
                className={`
                  mt-2 text-xs font-medium hidden sm:block
                  ${isCurrent ? 'text-indigo-400' : 'text-slate-500'}
                `}
              >
                {stepTitles[step - 1] || `Step ${step}`}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
