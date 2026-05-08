import PDFViewer from './PDFViewer.jsx';

// PPTX (and DOC/DOCX/XLSX/XLS/PPT when used here) are converted server-side
// to PDF via LibreOffice. Reuse PDFViewer for rendering, highlighting, scrolling.
export default function PptxViewer({ filename, passage }) {
  return <PDFViewer filename={filename} passage={passage} endpoint="/api/file-preview/" />;
}
