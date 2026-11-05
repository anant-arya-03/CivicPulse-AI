"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, ArrowRight, Info, Loader2, LocateFixed, MapPin, Search } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";

import { LocationMap, type MapPoint } from "@/components/complaints/location-map-loader";
import { FormAlert } from "@/components/shared/form-alert";
import { FormField, fieldAria } from "@/components/shared/form-field";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { locationsApi } from "@/features/complaints/api";
import { useLocationSearch, useUpdateComplaint } from "@/features/complaints/hooks";
import {
  locationSchema,
  toLocationPayload,
  type LocationValues,
} from "@/features/complaints/schemas";
import { isApiError } from "@/lib/api-client";
import type { Complaint, LocationResult } from "@/types/api";

interface LocationStepProps {
  complaint: Complaint;
  onBack: () => void;
  onSaved: () => void;
}

export function LocationStep({ complaint, onBack, onSaved }: LocationStepProps) {
  const updateComplaint = useUpdateComplaint(complaint.id);

  const [searchInput, setSearchInput] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const search = useLocationSearch(submittedQuery);

  // An address suggested for a pin the user placed. Applied only if they choose to.
  const [suggestion, setSuggestion] = useState<LocationResult | null>(null);
  const [pinMessage, setPinMessage] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);

  const {
    register,
    control,
    handleSubmit,
    setValue,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LocationValues>({
    resolver: zodResolver(locationSchema),
    defaultValues: {
      addressLine: complaint.address_line ?? "",
      locality: complaint.locality ?? "",
      city: complaint.city ?? "",
      state: complaint.state ?? "",
      postalCode: complaint.postal_code ?? "",
      country: complaint.country ?? "",
      latitude: complaint.latitude,
      longitude: complaint.longitude,
      confirmed: false,
    },
  });

  const latitude = useWatch({ control, name: "latitude" });
  const longitude = useWatch({ control, name: "longitude" });
  const point: MapPoint | null =
    latitude !== null && longitude !== null ? { latitude, longitude } : null;

  function applyAddress(result: LocationResult) {
    const options = { shouldDirty: true, shouldValidate: true };
    setValue("addressLine", result.address_line ?? "", options);
    setValue("locality", result.locality ?? "", options);
    setValue("city", result.city ?? "", options);
    setValue("state", result.state ?? "", options);
    setValue("postalCode", result.postal_code ?? "", options);
    setValue("country", result.country ?? "", options);
    setValue("latitude", result.latitude, options);
    setValue("longitude", result.longitude, options);
    setSuggestion(null);
  }

  async function placePin(next: MapPoint) {
    setValue("latitude", next.latitude, { shouldDirty: true });
    setValue("longitude", next.longitude, { shouldDirty: true });
    setPinMessage(null);
    try {
      const { result } = await locationsApi.reverse(next.latitude, next.longitude);
      setSuggestion(result);
    } catch {
      setSuggestion(null);
      setPinMessage("Pin placed. We couldn't look up the address, so please type it below.");
    }
  }

  function locateMe() {
    if (!("geolocation" in navigator)) {
      setPinMessage("Your browser can't share its location. Please search or place the pin.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocating(false);
        void placePin({ latitude: position.coords.latitude, longitude: position.coords.longitude });
      },
      () => {
        setLocating(false);
        setPinMessage("We couldn't get your location. Please search or place the pin on the map.");
      },
      { enableHighAccuracy: true, timeout: 10_000 },
    );
  }

  function handleSearch(event: FormEvent) {
    event.preventDefault();
    setSubmittedQuery(searchInput.trim());
  }

  async function onSubmit(values: LocationValues) {
    try {
      await updateComplaint.mutateAsync(toLocationPayload(values));
      onSaved();
    } catch (error) {
      setError("root", {
        message: isApiError(error) ? error.message : "Couldn't save the location. Please try again.",
      });
    }
  }

  return (
    <div className="grid gap-6">
      <div className="grid gap-1">
        <h2 className="text-xl font-semibold">Where is the problem?</h2>
        <p className="text-sm text-muted-foreground">
          Search for the address, place a pin on the map, or type it in. We never guess the
          location from your photo.
        </p>
      </div>

      {/* Search runs only when the user submits, never while typing (provider usage rules). */}
      <form onSubmit={handleSearch} role="search" className="grid gap-2">
        <Label htmlFor="location-search">Search for an address or landmark</Label>
        <div className="flex gap-2">
          <Input
            id="location-search"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="e.g. Lake Road, Lakeside"
            autoComplete="off"
          />
          <Button type="submit" variant="outline" disabled={searchInput.trim().length < 3}>
            {search.isFetching ? <Loader2 className="animate-spin" aria-hidden /> : <Search aria-hidden />}
            Search
          </Button>
        </div>
      </form>

      {search.data?.provider === "mock" && (
        <p className="flex items-start gap-2 rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground">
          <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          Address search is using sample locations in a fictional &quot;Demo City&quot;. See the
          project docs to switch on real address search.
        </p>
      )}
      {search.isError && (
        <FormAlert message={isApiError(search.error) ? search.error.message : "Search failed."} />
      )}
      {search.data && (
        <ul className="grid gap-2" aria-label="Search results">
          {search.data.results.length === 0 && (
            <li className="text-sm text-muted-foreground">No places found. Try a different search.</li>
          )}
          {search.data.results.map((result) => (
            <li key={`${result.latitude},${result.longitude},${result.label}`}>
              <button
                type="button"
                onClick={() => applyAddress(result)}
                className="flex w-full items-start gap-2 rounded-lg border border-border bg-card px-3 py-2.5 text-left text-sm hover:border-teal hover:bg-teal-soft/40 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              >
                <MapPin className="mt-0.5 size-4 shrink-0 text-teal" aria-hidden />
                {result.label}
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="grid gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-medium">Map {point ? "" : "(click to place a pin)"}</p>
          <Button type="button" variant="ghost" size="sm" onClick={locateMe} disabled={locating}>
            {locating ? <Loader2 className="animate-spin" aria-hidden /> : <LocateFixed aria-hidden />}
            Use my current location
          </Button>
        </div>
        <div className="h-72 overflow-hidden rounded-xl border border-border sm:h-80">
          <LocationMap point={point} onPick={(p) => void placePin(p)} className="h-full w-full" />
        </div>
        {pinMessage && <p className="text-sm text-muted-foreground">{pinMessage}</p>}
        {suggestion && (
          <div className="flex flex-col gap-2 rounded-lg border border-teal/40 bg-teal-soft/50 p-3 text-sm sm:flex-row sm:items-center sm:justify-between">
            <span>
              <span className="font-medium">Address near the pin:</span> {suggestion.label}
            </span>
            <Button type="button" size="sm" variant="outline" onClick={() => applyAddress(suggestion)}>
              Use this address
            </Button>
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid gap-5">
        <FormAlert message={errors.root?.message ?? errors.latitude?.message} />

        <FormField id="addressLine" label="Street address or landmark" error={errors.addressLine?.message}>
          <Input
            autoComplete="street-address"
            {...fieldAria("addressLine", errors.addressLine?.message)}
            {...register("addressLine")}
          />
        </FormField>

        <div className="grid gap-5 sm:grid-cols-2">
          <FormField id="locality" label="Neighbourhood / ward (optional)" error={errors.locality?.message}>
            <Input {...fieldAria("locality", errors.locality?.message)} {...register("locality")} />
          </FormField>
          <FormField id="city" label="City or town" error={errors.city?.message}>
            <Input
              autoComplete="address-level2"
              {...fieldAria("city", errors.city?.message)}
              {...register("city")}
            />
          </FormField>
          <FormField id="state" label="State / region (optional)" error={errors.state?.message}>
            <Input
              autoComplete="address-level1"
              {...fieldAria("state", errors.state?.message)}
              {...register("state")}
            />
          </FormField>
          <div className="grid grid-cols-2 items-start gap-3">
            <FormField id="postalCode" label="Postal code" error={errors.postalCode?.message}>
              <Input
                autoComplete="postal-code"
                {...fieldAria("postalCode", errors.postalCode?.message)}
                {...register("postalCode")}
              />
            </FormField>
            <FormField
              id="country"
              label="Country code"
              hint="e.g. IN, US"
              error={errors.country?.message}
            >
              <Input
                maxLength={2}
                className="uppercase"
                autoComplete="country"
                {...fieldAria("country", errors.country?.message, "e.g. IN, US")}
                {...register("country")}
              />
            </FormField>
          </div>
        </div>

        <Controller
          control={control}
          name="confirmed"
          render={({ field }) => (
            <div className="grid gap-2">
              <div className="flex items-start gap-3 rounded-lg border border-border bg-card p-3">
                <Checkbox
                  id="confirmed"
                  checked={field.value}
                  onCheckedChange={(checked) => field.onChange(checked === true)}
                  aria-invalid={errors.confirmed ? true : undefined}
                  aria-describedby={errors.confirmed ? "confirmed-error" : undefined}
                  className="mt-0.5"
                />
                <Label htmlFor="confirmed" className="leading-snug font-normal">
                  I confirm this is where the problem is.
                </Label>
              </div>
              {errors.confirmed && (
                <p id="confirmed-error" role="alert" className="text-sm text-error-strong">
                  {errors.confirmed.message}
                </p>
              )}
            </div>
          )}
        />

        <div className="flex justify-between gap-3">
          <Button type="button" variant="outline" size="lg" onClick={onBack}>
            <ArrowLeft aria-hidden /> Back
          </Button>
          <Button type="submit" size="lg" disabled={isSubmitting}>
            {isSubmitting && <Loader2 className="animate-spin" aria-hidden />}
            Continue <ArrowRight aria-hidden />
          </Button>
        </div>
      </form>
    </div>
  );
}
