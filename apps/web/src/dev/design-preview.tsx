import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { DesignPreview } from './DecisionPreview';
import '../index.css';

if (import.meta.env.DEV) createRoot(document.getElementById('root')!).render(<MemoryRouter><DesignPreview /></MemoryRouter>);
