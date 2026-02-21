'use client';



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
        <div
          className="absolute top-0 left-0 h-full bg-indigo-600 transition-all duration-300"
          style={{ width: `${(currentStep / totalSteps) * 100}%` }}
        />
      </div>

      {/* Step circles */}
      <div className="flex items-center justify-between">
        {Array.from({ length: totalSteps }, (_, i) => i + 1).map((step) => {
          const isCompleted = step < currentStep;
          const isCurrent = step === currentStep;

          return (
            <div key={step} className="flex flex-col items-center flex-1">
              <div
                className={`
                  w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold
                  transition-all duration-200 border-2
                  ${
                    isCompleted || isCurrent
                      ? 'bg-indigo-600 text-white border-indigo-600 scale-110'
                      : 'bg-slate-800 text-slate-400 border-slate-700 scale-100'
                  }
                `}
              >
                {isCompleted ? (
                  <span>✓</span>
                ) : (
                  step
                )}
              </div>
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
