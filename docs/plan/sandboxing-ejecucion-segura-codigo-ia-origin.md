---
id: sandboxing-ejecucion-segura-codigo-ia-origin
title: SafeExec — de qué evidencia sale
type: neuron-plan
market: AI devtools
created: '2026-08-16'
updated: '2026-08-16'
sources:
- 170421160e80ac8c
- 278104a174355bd6
tags: []
base_confidence: 0.8
half_life_days: 365
last_reinforced: '2026-08-16'
provenance:
  scope: M
  ref: null
links:
- to: sandboxing-ejecucion-segura-codigo-ia
  type: derived_from
---

## Nota fuente
[[sandboxing-ejecucion-segura-codigo-ia]] — Infraestructura de ejecución segura de código generado por IA

## Qué es
Infraestructura de ejecución segura de código autónomo: MicroVMs en Rust que arrancan en milisegundos con SDKs en Python/Rust/TS [170421160e80ac8c], y contenerización de agentes/dev tools para mantenerlos aislados en el sistema local [278104a174355bd6].

## Evidencia
Sub-tema activo dentro del cluster de AI dev tools [sig-a73b51ab47bb].

## Por qué importa
Tiene fundamentos técnicos sólidos y encaja con la ola de código autónomo generado por agentes [sig-a73b51ab47bb].

Comparte el riesgo de comoditizarse como feature de plataforma.

## Conexiones
- relates_to → [[micro-herramientas-features-no-productos]]

## Riesgos heredados y propios
- Comoditización: el patrón vecino advierte que sandboxes de ejecución son feature absorbible por plataformas (OpenAI ya libera dev tools); mantener el alcance mínimo y la interfaz Sandbox reemplazable
- Aislamiento insuficiente: contenedores dan menos garantía que MicroVM/gVisor; escape de sandbox es riesgo de seguridad — mitigar con no-root, sin red, read-only y evaluar runsc antes de exponer público
- Dependencia del Docker daemon/host: requiere privilegios en el host y complica el deploy managed; documentar y aislar en adapter
- DoS por consumo de recursos: ejecuciones concurrentes pueden agotar el host — requiere límite de concurrencia y cuotas
- Latencia de arranque de contenedor vs promesa de 'milisegundos' de MicroVM: puede no satisfacer casos de baja latencia; medir y decidir migración si el uso lo exige
