'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/Card';

interface BioVariant {
  bio_type: string;
  bio_text: string;
  validation_status: string;
}

interface PersonaPreviewProps {
  twinId: string | null;
  onActivate: () => void;
}

export function PersonaPreview({ twinId, onActivate }: PersonaPreviewProps) {
  const [bios, setBios] = useState<BioVariant[]>([]);
  const [selectedBioType, setSelectedBioType] = useState<string>('short');
  const [loading, setLoading] = useState(true);
  const [activating, setActivating] = useState(false);
  const [twinName, setTwinName] = useState('');

  useEffect(() => {
    if (!twinId) return;

    const fetchData = async () => {
      try {
        // Fetch bios
        const biosRes = await fetch(`/api/persona/link-compile/twins/${twinId}/bios`);
        if (biosRes.ok) {
          const data = await biosRes.json();
          setBios(data.variants || []);
        }

        // Fetch twin info
        const twinRes = await fetch(`/api/twins/${twinId}`);
        if (twinRes.ok) {
          const twin = await twinRes.json();
          setTwinName(twin.name);
        }
      } catch (e) {
        console.error('Failed to load preview:', e);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [twinId]);

  const selectedBio = bios.find(b => b.bio_type === selectedBioType);
  const validBios = bios.filter(b => b.validation_status === 'valid');

  const handleActivate = async () => {
    setActivating(true);
    try {
      const response = await fetch(`/api/twins/${twinId}/activate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ final_name: twinName }),
      });

      if (response.ok) {
        onActivate();
      } else {
        throw new Error('Activation failed');
      }
    } catch (e) {
      alert('Failed to activate twin. Please try again.');
    } finally {
      setActivating(false);
    }
  };

  const bioTypeLabels: Record<string, string> = {
    one_liner: 'One-Liner',
    short: 'Short Bio',
    linkedin_about: 'LinkedIn About',
    speaker_intro: 'Speaker Intro',
    full: 'Full Bio',
  };

  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-slate-400">Building your persona...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold mb-2 text-white">Your Persona is Ready!</h2>
        <p className="text-slate-400">
          Review your generated bio and activate your Digital Twin.
        </p>
      </div>

      {/* Bio Selector */}
      <div className="flex gap-2 flex-wrap">
        {validBios.map((bio) => (
          <button
            key={bio.bio_type}
            onClick={() => setSelectedBioType(bio.bio_type)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              selectedBioType === bio.bio_type
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
            }`}
          >
            {bioTypeLabels[bio.bio_type] || bio.bio_type}
          </button>
        ))}
      </div>

      {/* Bio Preview */}
      {selectedBio ? (
        <Card className="p-6 bg-slate-900 border-slate-700">
          <h3 className="text-sm font-medium text-slate-400 mb-3">
            {bioTypeLabels[selectedBio.bio_type]}
          </h3>
          <p className="text-white whitespace-pre-wrap">{selectedBio.bio_text}</p>
          <div className="mt-4 flex items-center gap-2">
            <span className="text-green-400 text-sm">✓ Validated</span>
            <span className="text-slate-500 text-sm">— All claims cited</span>
          </div>
        </Card>
      ) : (
        <Card className="p-6 bg-slate-900 border-slate-700 text-center">
          <p className="text-slate-400">No valid bio generated. You may need more content.</p>
        </Card>
      )}

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-slate-900 p-4 rounded-lg text-center border border-slate-700">
          <div className="text-2xl font-bold text-indigo-400">{validBios.length}</div>
          <div className="text-sm text-slate-400">Bio Variants</div>
        </div>
        <div className="bg-slate-900 p-4 rounded-lg text-center border border-slate-700">
          <div className="text-2xl font-bold text-indigo-400">5</div>
          <div className="text-sm text-slate-400">Persona Layers</div>
        </div>
        <div className="bg-slate-900 p-4 rounded-lg text-center border border-slate-700">
          <div className="text-2xl font-bold text-indigo-400">✓</div>
          <div className="text-sm text-slate-400">Citations Ready</div>
        </div>
      </div>

      {/* Activation CTA */}
      <button
        onClick={handleActivate}
        disabled={activating || !twinName.trim()}
        className="w-full py-4 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-semibold text-lg transition-colors flex items-center justify-center gap-2"
      >
        {activating ? (
          <>
            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            Activating...
          </>
        ) : (
          <>
            <span>✨</span>
            Activate Digital Twin
          </>
        )}
      </button>

      <p className="text-center text-sm text-slate-500">
        After activation, you can chat with your Digital Twin. You can always add more content later.
      </p>
    </div>
  );
}
