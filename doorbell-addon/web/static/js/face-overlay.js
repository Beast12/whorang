/**
 * FaceOverlay — renders SVG bounding boxes over event images.
 * Usage: FaceOverlay.render(containerEl, imageSrc, eventId)
 */
window.FaceOverlay = (function () {
    // One ResizeObserver per <img>, so re-opening the same modal doesn't pile
    // up observers, and so we redraw whenever the image's rendered size
    // actually changes — including the first time it goes from 0×0 (still
    // inside a not-yet-shown Bootstrap modal, whose fade transition isn't
    // finished when the image's "load" event fires) to its real size.
    const _observers = new WeakMap();

    function _removeSvg(container) {
        const existing = container.querySelector('.face-overlay-svg');
        if (existing) existing.remove();
    }

    function _drawOverlay(container, img, faces) {
        _removeSvg(container);
        if (!faces || faces.length === 0) return;

        const scaleX = img.clientWidth / img.naturalWidth;
        const scaleY = img.clientHeight / img.naturalHeight;

        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.classList.add('face-overlay-svg');
        svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
        svg.style.cssText = [
            'position:absolute',
            'top:0',
            'left:0',
            `width:${img.clientWidth}px`,
            `height:${img.clientHeight}px`,
            'pointer-events:none',
            'overflow:visible',
        ].join(';');

        faces.forEach(function (face) {
            const [fx, fy, fw, fh] = face.bbox;
            const x = Math.round(fx * scaleX);
            const y = Math.round(fy * scaleY);
            const w = Math.round(fw * scaleX);
            const h = Math.round(fh * scaleY);
            const isKnown = face.name && face.name !== 'Unknown';
            const color = isKnown ? '#38bdf8' : '#fb923c';
            const label = isKnown
                ? `${face.name} (${Math.round(face.score * 100)}%)`
                : 'Unknown';

            const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            rect.setAttribute('x', x);
            rect.setAttribute('y', y);
            rect.setAttribute('width', w);
            rect.setAttribute('height', h);
            rect.setAttribute('fill', 'none');
            rect.setAttribute('stroke', color);
            rect.setAttribute('stroke-width', '2');
            rect.setAttribute('rx', '3');
            svg.appendChild(rect);

            const textY = y > 20 ? y - 4 : y + h + 14;

            const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            const approxTextWidth = label.length * 6.5 + 8;
            bg.setAttribute('x', x);
            bg.setAttribute('y', textY - 12);
            bg.setAttribute('width', approxTextWidth);
            bg.setAttribute('height', 14);
            bg.setAttribute('fill', color);
            bg.setAttribute('rx', '2');
            svg.appendChild(bg);

            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', x + 4);
            text.setAttribute('y', textY - 1);
            text.setAttribute('fill', '#fff');
            text.setAttribute('font-size', '11');
            text.setAttribute('font-family', 'sans-serif');
            text.setAttribute('font-weight', '600');
            text.textContent = label;
            svg.appendChild(text);
        });

        container.appendChild(svg);
    }

    async function render(containerEl, imageSrc, eventId) {
        if (!containerEl || !eventId) return;
        containerEl.style.position = 'relative';
        containerEl.style.display = 'inline-block';

        let faces;
        try {
            const resp = await fetch(`api/events/${eventId}/faces`);
            if (!resp.ok) return;
            const data = await resp.json();
            faces = data.faces || [];
        } catch (e) {
            return;
        }

        if (!faces.length) return;

        // Find or wait for the image in the container
        let img = containerEl.querySelector('img');
        if (!img) return;

        function doDraw() {
            // Not laid out yet (e.g. still inside a Bootstrap modal mid fade-in) —
            // skip and wait for the ResizeObserver to fire again once it is.
            if (!img.clientWidth || !img.clientHeight) return;
            _drawOverlay(containerEl, img, faces);
        }

        const existing = _observers.get(img);
        if (existing) existing.disconnect();
        const observer = new ResizeObserver(doDraw);
        observer.observe(img);
        _observers.set(img, observer);

        if (img.complete && img.naturalWidth) {
            requestAnimationFrame(doDraw);
        } else {
            img.addEventListener('load', function () {
                requestAnimationFrame(doDraw);
            }, { once: true });
        }
    }

    return { render };
})();
