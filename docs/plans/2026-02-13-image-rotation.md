# Image Rotation Feature Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow users to rotate individual unwarped images from the viewer's image explorer modal, with per-image angle input, and show rotated versions when they exist.

**Architecture:** The viewer backend (FastAPI) gets 3 new endpoints: rotate (invokes lambda), delete-rotated (S3 delete), and the existing `get_unwarped_images` is extended to also check for `_rotated` variants. The frontend adds a rotation angle input in the modal header and per-image rotate/unrotate buttons on each unwarped card.

**Tech Stack:** Python/FastAPI, boto3, vanilla JavaScript

---

### Task 1: Extend `get_unwarped_images` to check for rotated variants

**Files:**
- Modify: `app/s3_service.py:302-342`

**Step 1: Add rotated image checking to `get_unwarped_images`**

In the `get_unwarped_images` function, after checking if each unwarped direction exists, also check if a `_rotated` variant exists. For each direction, compute the rotated key as `{unwarped_key_without_ext}_rotated.jpg` and do a `head_object` check. Add `rotated_exists`, `rotated_key`, and `rotated_url` fields to the result dict.

```python
# Inside the for loop, after the existing exists/url logic:
# Check for rotated variant
rotated_key = f"{unwarped_prefix}{base_name}_{direction}_rotated.jpg"
try:
    s3.head_object(Bucket=BUCKET_NAME, Key=rotated_key)
    rotated_exists = True
    rotated_url = get_presigned_url(rotated_key)
except ClientError:
    rotated_exists = False
    rotated_url = None

result[direction] = {
    "exists": exists,
    "key": unwarped_key,
    "url": url,
    "direction": direction.capitalize(),
    "rotated_exists": rotated_exists,
    "rotated_key": rotated_key,
    "rotated_url": rotated_url,
}
```

**Step 2: Commit**

```bash
git add app/s3_service.py
git commit -m "feat: check for rotated image variants in get_unwarped_images"
```

---

### Task 2: Add rotate and delete-rotated API endpoints

**Files:**
- Modify: `app/main.py` (add after the `unwarp_image` endpoint, around line 338)

**Step 1: Add `POST /api/rotate` endpoint**

This endpoint takes `image_key` (the unwarped S3 key, e.g. `unwarped/2026/01/26/reolink_00_20260126233811_north.jpg`) and `angle` (float). It invokes the lambda with `rotate=True`.

```python
@app.post("/api/rotate")
async def rotate_image(image_key: str, angle: float) -> dict[str, Any]:
    """Rotate an unwarped image by a given angle via Lambda.

    Args:
        image_key: S3 key of the unwarped image
        angle: Rotation angle in degrees clockwise
    """
    try:
        s3_uri = s3_service.get_s3_uri(image_key)

        lambda_client = boto3.client('lambda', region_name=s3_service.AWS_REGION)

        payload = {
            "input_s3_uri": s3_uri,
            "rotate": True,
            "rotation_angle": angle,
        }

        response = lambda_client.invoke(
            FunctionName='vibecast-process-image',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )

        response_payload = json.loads(response['Payload'].read())

        body = response_payload.get('body', {})
        if isinstance(body, str):
            body = json.loads(body)

        if response_payload.get('statusCode') != 200:
            error_msg = body.get('error', 'Unknown error')
            raise HTTPException(
                status_code=response_payload.get('statusCode', 500),
                detail=f"Lambda error: {error_msg}"
            )

        return body

    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e)
        if "credentials" in error_str.lower():
            raise HTTPException(status_code=500, detail=f"AWS credentials error: {error_str}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Step 2: Add `DELETE /api/rotated` endpoint**

This endpoint takes `image_key` (the original unwarped key), computes `_rotated` key, and deletes it from S3.

```python
@app.delete("/api/rotated")
async def delete_rotated_image(image_key: str) -> dict[str, Any]:
    """Delete the rotated variant of an unwarped image.

    Args:
        image_key: S3 key of the original unwarped image (not the rotated one)
    """
    try:
        # Compute rotated key from original key
        name_without_ext, ext = image_key.rsplit(".", 1)
        rotated_key = f"{name_without_ext}_rotated.{ext}"

        s3 = s3_service.get_s3_client()
        s3.delete_object(Bucket=s3_service.BUCKET_NAME, Key=rotated_key)

        return {"deleted": rotated_key}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Step 3: Commit**

```bash
git add app/main.py
git commit -m "feat: add rotate and delete-rotated API endpoints"
```

---

### Task 3: Add rotation UI to the modal header

**Files:**
- Modify: `app/templates/viewer.html` (modal header, around line 1334)

**Step 1: Add rotation angle input to modal header**

In the modal header's button area (the `div` with `display: flex; gap: 10px; align-items: center;` around line 1334), add a rotation angle input field. Place it after the unwarp button but before the close button.

Find this block (lines 1334-1343):
```html
<div style="display: flex; gap: 10px; align-items: center;">
    <button class="btn btn-primary" id="unwarpButton" onclick="manualUnwarp()" style="display: none;">
        Unwarp This Image
    </button>
    <button class="btn btn-success" id="modalProcessButton" onclick="goToProcessTab()" style="display: none;">
        Process Images
    </button>
    <span id="unwarpStatus" style="color: #888; font-size: 0.9em;"></span>
    <button class="modal-close" onclick="closeModal()">&times;</button>
</div>
```

Replace with:
```html
<div style="display: flex; gap: 10px; align-items: center;">
    <button class="btn btn-primary" id="unwarpButton" onclick="manualUnwarp()" style="display: none;">
        Unwarp This Image
    </button>
    <button class="btn btn-success" id="modalProcessButton" onclick="goToProcessTab()" style="display: none;">
        Process Images
    </button>
    <div id="rotationControls" style="display: none; align-items: center; gap: 6px;">
        <label style="font-size: 0.85em; white-space: nowrap;">Rotation:</label>
        <input type="number" id="rotationAngle" placeholder="0" step="any"
               style="width: 70px; padding: 4px 6px; border: 1px solid #555; border-radius: 4px; background: #2a2a2a; color: #fff; font-size: 0.85em;">
        <span style="font-size: 0.85em;">deg</span>
    </div>
    <span id="unwarpStatus" style="color: #888; font-size: 0.9em;"></span>
    <button class="modal-close" onclick="closeModal()">&times;</button>
</div>
```

**Step 2: Commit**

```bash
git add app/templates/viewer.html
git commit -m "feat: add rotation angle input to modal header"
```

---

### Task 4: Add rotate/unrotate buttons to unwarped image cards

**Files:**
- Modify: `app/templates/viewer.html` (the `showUnwarped` function, around line 1903)

**Step 1: Update the unwarped image card rendering in `showUnwarped`**

Modify the `showUnwarped` function to:
1. Show the `rotationControls` div when unwarped images exist
2. For each direction, show the rotated image if it exists (instead of the original)
3. Add a "Rotate" button on each card (reads angle from shared input)
4. Add an "Unrotate" button on cards that have a rotated variant

In the section that builds gridHTML for unwarped images (around line 1903), replace the directions map:

```javascript
gridHTML += directions.map(dir => {
    const item = data.unwarped[dir];
    if (item && item.exists) {
        const s3Key = item.key || '';
        const displayUrl = item.rotated_exists ? item.rotated_url : item.url;
        const displayLabel = item.rotated_exists ? `${item.direction} (rotated)` : item.direction;
        return `
            <div class="unwarped-item" data-url="${displayUrl}" data-label="${displayLabel}">
                <div class="direction">
                    <span>${displayLabel}</span>
                    <input type="checkbox" class="selection-checkbox"
                           onclick="event.stopPropagation(); toggleImageSelection('${displayUrl}', '${item.direction}', '${s3Key}')">
                </div>
                <img src="${displayUrl}" alt="${item.direction}" onclick="openFullscreen('${displayUrl}', '${displayLabel}')" style="cursor: zoom-in;">
                <div style="display: flex; gap: 4px; padding: 4px;">
                    <button class="btn btn-secondary" style="flex: 1; padding: 2px 6px; font-size: 0.75em;"
                            onclick="event.stopPropagation(); rotateImage('${s3Key}')">
                        Rotate
                    </button>
                    ${item.rotated_exists ? `
                    <button class="btn btn-secondary" style="flex: 1; padding: 2px 6px; font-size: 0.75em; color: #f44336;"
                            onclick="event.stopPropagation(); unrotateImage('${s3Key}')">
                        Unrotate
                    </button>
                    ` : ''}
                </div>
            </div>
        `;
    } else {
        return `
            <div class="unwarped-item not-available">
                <div class="direction">${dir}</div>
                <div class="not-found">Not available</div>
            </div>
        `;
    }
}).join('');
```

Also, after the `anyExist` check (around line 1876), show/hide the rotation controls:

```javascript
// Show rotation controls if unwarped images exist
document.getElementById('rotationControls').style.display = anyExist ? 'flex' : 'none';
```

**Step 2: Commit**

```bash
git add app/templates/viewer.html
git commit -m "feat: add rotate/unrotate buttons to unwarped image cards"
```

---

### Task 5: Add `rotateImage` and `unrotateImage` JavaScript functions

**Files:**
- Modify: `app/templates/viewer.html` (add after the `manualUnwarp` function, around line 2009)

**Step 1: Add the rotate function**

```javascript
async function rotateImage(imageKey) {
    const angleInput = document.getElementById('rotationAngle');
    const angle = parseFloat(angleInput.value);
    if (isNaN(angle) || angle === 0) {
        alert('Please enter a non-zero rotation angle.');
        return;
    }

    const unwarpStatus = document.getElementById('unwarpStatus');
    unwarpStatus.innerHTML = '<div class="spinner"></div> Rotating...';

    try {
        const response = await fetch(`/api/rotate?image_key=${encodeURIComponent(imageKey)}&angle=${angle}`, {
            method: 'POST'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Rotation failed');
        }

        unwarpStatus.textContent = 'Rotation complete! Refreshing...';

        // Refresh the modal to show rotated image
        setTimeout(() => {
            showUnwarped(currentImageKey, currentImageFilename, currentImageIndex);
        }, 1000);

    } catch (error) {
        unwarpStatus.textContent = `Error: ${error.message}`;
    }
}

async function unrotateImage(imageKey) {
    const unwarpStatus = document.getElementById('unwarpStatus');
    unwarpStatus.innerHTML = '<div class="spinner"></div> Removing rotation...';

    try {
        const response = await fetch(`/api/rotated?image_key=${encodeURIComponent(imageKey)}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Unrotate failed');
        }

        unwarpStatus.textContent = 'Rotation removed! Refreshing...';

        // Refresh the modal
        setTimeout(() => {
            showUnwarped(currentImageKey, currentImageFilename, currentImageIndex);
        }, 1000);

    } catch (error) {
        unwarpStatus.textContent = `Error: ${error.message}`;
    }
}
```

**Step 2: Commit**

```bash
git add app/templates/viewer.html
git commit -m "feat: add rotateImage and unrotateImage JavaScript functions"
```

---

### Task 6: Manual testing checklist

After all changes are in place, verify:

1. Open viewer, select a date with images, click an image to open the modal
2. If unwarped images exist, the rotation angle input should be visible in the header
3. Enter an angle (e.g. 15), click "Rotate" on one of the direction cards
4. After rotation completes, the card should show the rotated image with "(rotated)" label
5. Click "Unrotate" on the rotated card — it should revert to the original
6. Verify fullscreen view shows the correct (rotated or original) version
7. Verify the rotation controls are hidden when no unwarped images exist
