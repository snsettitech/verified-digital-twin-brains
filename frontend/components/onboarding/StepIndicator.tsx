'use client';

import { motion } from 'framer-motion';
import { Check } from 'lucide-react';

interface StepIndicatorProps {
  currentStep: number;
  totalSteps: number;
  stepTitles: string[];
}

export function StepIndicator({ currentStep, totalSteps, stepTitles }: StepIndicatorProps) {
  return (
    <div className="w-full">
      {/* Progress bar */}
      <div className="relative h-2 bg-muted rounded-full overflow-hidden mb-6">
        <motion.div
          className="absolute top-0 left-0 h-full bg-primary"
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
          const isPending = step > currentStep;

          return (
            <div key={step} className="flex flex-col items-center flex-1">
              <motion.div
                initial={false}
                animate={{
                  scale: isCurrent ? 1.1 : 1,
                }}
                className={`
                  w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold
                  transition-colors duration-200 border-2
                  ${
                    isCompleted
                      ? 'bg-primary text-primary-foreground border-primary'
                      : isCurrent
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'bg-background text-muted-foreground border-muted'
                  }
                `}
              >
                {isCompleted ? (
                  <Check className="h-5 w-5" />
                ) : (
                  step
                )}
              </motion.div>
              <span
                className={`
                  mt-2 text-xs font-medium hidden sm:block
                  ${isCurrent ? 'text-primary' : 'text-muted-foreground'}
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
