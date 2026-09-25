#pragma once
void Gfx_SetupDL_25Xlu(GraphicsContext*);
void Matrix_Push(void);
void Matrix_Pop(void);
void Matrix_ReplaceRotation(MtxF*);
void Matrix_Scale(float,float,float,int);
Mtx* Matrix_NewMtx(GraphicsContext*,char*,int);
void gSPVertex(Gfx* pkt, uintptr_t v, int n, int v0);
